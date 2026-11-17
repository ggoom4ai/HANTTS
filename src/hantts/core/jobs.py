"""합성 작업 대기열. 워커 응답은 UI 스레드 시그널로만 돌아온다."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from hantts.core.audio.pipeline import render
from hantts.core.config import AppConfig
from hantts.core.paths import DataPaths
from hantts.core.schema import CapabilitySchema
from hantts.core.store import DictEntry, Store
from hantts.core.supervisor import WorkerSupervisor
from hantts.core.text.frontend import prepare


@dataclass(slots=True)
class Rendered:
    path: str
    duration: float
    sample_rate: int
    audio: np.ndarray
    text: str
    engine_id: str
    voice: str
    lang: str
    params: dict[str, Any]


@dataclass(slots=True)
class _Job:
    engine_id: str
    lang: str
    voice: str
    text: str
    params: dict[str, Any]
    out_path: Path
    normalize: bool
    acronyms: bool
    target_sr: int
    lufs: float | None
    silence_ms: int
    write_srt: bool
    record: bool = True
    entries: list[DictEntry] = field(default_factory=list)
    chunks: list[Any] = field(default_factory=list)
    paths: list[Path] = field(default_factory=list)
    durations: list[float] = field(default_factory=list)
    words: list[tuple[float, float, str]] = field(default_factory=list)
    index: int = 0
    session: Path = field(default_factory=Path)


class _RenderThread(QThread):
    done = Signal()
    failed = Signal(str)

    def __init__(self, job: _Job) -> None:
        super().__init__()
        self.job = job
        self.rendered: Rendered | None = None

    def run(self) -> None:
        try:
            cues = self.job.words or _sentence_cues(self.job)
            audio, sr, duration = render(
                self.job.paths,
                silence_ms=self.job.silence_ms,
                target_sr=self.job.target_sr,
                lufs=self.job.lufs,
                out_path=self.job.out_path,
                cues=cues if self.job.write_srt else None,
            )
            self.rendered = Rendered(
                str(self.job.out_path),
                duration,
                sr,
                audio,
                self.job.text,
                self.job.engine_id,
                self.job.voice,
                self.job.lang,
                dict(self.job.params),
            )
            self.done.emit()
        except Exception as e:  # noqa: BLE001 — 스레드 밖으로는 메시지만 보낸다
            self.failed.emit(str(e))


class JobQueue(QObject):
    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(str)
    schema_ready = Signal(str, object)

    def __init__(
        self, paths: DataPaths, config: AppConfig, store: Store, supervisor: WorkerSupervisor
    ) -> None:
        super().__init__()
        self.paths = paths
        self.config = config
        self.store = store
        self.supervisor = supervisor
        self._job: _Job | None = None
        self._render: _RenderThread | None = None
        self._schema: dict[str, CapabilitySchema] = {}
        self._retries = 0
        self._retry_pending = False
        self.supervisor.ready.connect(self._resume)
        self.supervisor.failed.connect(self._worker_failed)

    def remember_schema(self, engine_id: str, schema: CapabilitySchema) -> None:
        self._schema[engine_id] = schema

    def refresh_schema(self, engine_id: str) -> None:
        def on_load(msg: dict[str, Any], eid: str = engine_id) -> None:
            self._after_load(eid, msg)

        self.supervisor.call(engine_id, "load", {}, on_load)

    def _after_load(self, engine_id: str, msg: dict[str, Any]) -> None:
        if "error" in msg:
            self.failed.emit(str(msg["error"].get("message") or "엔진을 불러오지 못했습니다."))
            return
        def on_schema(desc: dict[str, Any], eid: str = engine_id) -> None:
            self._got_schema(eid, desc)

        self.supervisor.call(engine_id, "describe", {}, on_schema)

    def _got_schema(self, engine_id: str, msg: dict[str, Any]) -> None:
        if "error" in msg:
            self.failed.emit(str(msg["error"].get("message") or "스키마를 읽지 못했습니다."))
            return
        schema = CapabilitySchema.from_dict(msg["result"])
        self._schema[engine_id] = schema
        self.schema_ready.emit(engine_id, schema)

    def start(
        self,
        *,
        engine_id: str,
        lang: str,
        voice: str,
        text: str,
        params: dict[str, Any],
        out_path: Path,
        normalize: bool,
        acronyms: bool,
        target_sr: int,
        lufs: float | None,
        write_srt: bool,
        preview: bool = False,
        record: bool = True,
    ) -> None:
        if self._job is not None:
            self.failed.emit("이미 생성 중입니다.")
            return
        schema = self._schema.get(engine_id)
        limit = schema.limits.max_chars_per_request if schema else 300
        builtin = bool(schema and schema.features.builtin_normalization and params.get("text_normalization"))
        silence = int(params.get("chunk_silence_ms") or self.config.chunk_silence_ms)
        chunks = prepare(
            text,
            default_voice=voice,
            entries=self.store.list_dict(engine_id),
            normalize=normalize and not builtin,
            acronyms=acronyms,
            max_chars=limit,
        )
        if preview:
            chunks = chunks[:1]
        if not chunks:
            self.failed.emit("읽을 문장이 없습니다.")
            return
        session = self.paths.tmp / f"session-{uuid.uuid4().hex[:8]}"
        session.mkdir(parents=True, exist_ok=True)
        self._retries = 0
        self._retry_pending = False
        self._job = _Job(
            engine_id,
            lang,
            voice,
            text,
            dict(params),
            out_path,
            normalize,
            acronyms,
            target_sr,
            lufs,
            silence,
            write_srt and not preview,
            record and not preview,
            chunks=chunks,
            session=session,
        )
        self.progress.emit(0, len(chunks))
        self._next()

    def cancel(self) -> None:
        job = self._job
        if job is None:
            return
        self.supervisor.cancel(job.engine_id)
        self._job = None
        self._retries = 0
        self._retry_pending = False
        self.failed.emit("생성을 중지했습니다.")

    def _next(self) -> None:
        job = self._job
        if job is None:
            return
        if job.index >= len(job.chunks):
            self._render = _RenderThread(job)
            self._render.done.connect(self._rendered)
            self._render.failed.connect(self._render_failed)
            self._render.start()
            return
        chunk = job.chunks[job.index]
        path = job.session / f"c{job.index:04d}.wav"
        params = dict(job.params)
        if "lang" in params:
            params["lang"] = job.lang
        self.supervisor.call(
            job.engine_id,
            "synthesize",
            {
                "text": chunk.text,
                "lang": job.lang,
                "voice": chunk.voice or job.voice,
                "out_path": str(path),
                "params": params,
                "stream": False,
                "seed": None,
            },
            self._on_chunk,
        )

    def _on_chunk(self, msg: dict[str, Any]) -> None:
        job = self._job
        if job is None:
            return
        if "error" in msg:
            message = str(msg["error"].get("message") or "합성에 실패했습니다.")
            if message.startswith("워커가 종료되었습니다") and self._retries < 2:
                self._retries += 1
                self._retry_pending = True
                return
            self._fail(message)
            return
        self._retries = 0
        result = msg["result"]
        job.paths.append(Path(str(result["path"])))
        duration = float(result.get("duration") or 0)
        cursor = sum(job.durations) + job.silence_ms / 1000 * len(job.durations)
        job.durations.append(duration)
        words = result.get("word_timestamps") or []
        if words:
            for word in words:
                job.words.append(
                    (cursor + float(word["start"]), cursor + float(word["end"]), str(word["text"]))
                )
        job.index += 1
        self._next()
        self.progress.emit(job.index, len(job.chunks))

    def _rendered(self) -> None:
        thread = self._render
        job = self._job
        self._job = None
        if thread is None or thread.rendered is None or job is None:
            return
        rendered = thread.rendered
        if job.record:
            self.store.add_history(
                engine_id=rendered.engine_id,
                voice=rendered.voice,
                lang=rendered.lang,
                text=rendered.text,
                path=rendered.path,
                duration=rendered.duration,
                params=rendered.params,
            )
        self.finished.emit(rendered)

    def _render_failed(self, message: str) -> None:
        self._fail(message)

    def _resume(self, engine_id: str) -> None:
        job = self._job
        if not self._retry_pending or job is None or job.engine_id != engine_id:
            return
        self._retry_pending = False
        self._next()

    def _worker_failed(self, engine_id: str, message: str) -> None:
        job = self._job
        if job is None or job.engine_id != engine_id:
            return
        self._fail(message)

    def _fail(self, message: str) -> None:
        self._job = None
        self._retries = 0
        self._retry_pending = False
        self.failed.emit(message)


def _sentence_cues(job: _Job) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    cursor = 0.0
    gap = job.silence_ms / 1000
    for chunk, duration in zip(job.chunks, job.durations, strict=True):
        cues.append((cursor, cursor + duration, chunk.text))
        cursor += duration + gap
    return cues
