"""앱 상태. 화면은 이 객체의 메서드만 호출한다."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from hantts.core.catalog import Catalog, EngineEntry
from hantts.core.config import AppConfig
from hantts.core.download import CancelToken
from hantts.core.errors import CancelledError
from hantts.core.installer import (
    INSTALLED,
    NOT_INSTALLED,
    Installer,
    ProgressEvent,
)
from hantts.core.jobs import JobQueue, Rendered
from hantts.core.paths import DataPaths
from hantts.core.schema import CapabilitySchema, VoiceSpec
from hantts.core.store import Store
from hantts.core.supervisor import WorkerSupervisor
from hantts.core.text.detect import detect_lang
from hantts.core.text.frontend import prepare
from hantts.engines.base import EngineContext, get_adapter_class


class _RemoveThread(QThread):
    succeeded = Signal(str)
    failed = Signal(str, str)

    def __init__(self, installer: Installer, engine_id: str) -> None:
        super().__init__()
        self.installer = installer
        self.engine_id = engine_id

    def run(self) -> None:
        try:
            self.installer.uninstall(self.engine_id)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(self.engine_id, str(e))
            return
        self.succeeded.emit(self.engine_id)


class _InstallThread(QThread):
    progressed = Signal(object)
    succeeded = Signal(str)
    failed = Signal(str, str)

    def __init__(self, installer: Installer, engine_id: str, find_links: Path | None = None) -> None:
        super().__init__()
        self.installer = installer
        self.engine_id = engine_id
        self.find_links = find_links
        self.token = CancelToken()

    def run(self) -> None:
        try:
            self.installer.install(
                self.engine_id,
                on_progress=self.progressed.emit,
                cancel=self.token,
                find_links=self.find_links,
            )
        except CancelledError:
            self.failed.emit(self.engine_id, "설치를 취소해 이전 상태로 되돌렸습니다.")
            return
        except Exception as e:  # noqa: BLE001
            self.failed.emit(self.engine_id, str(e))
            return
        self.succeeded.emit(self.engine_id)

    def cancel(self) -> None:
        self.token.cancel()


class Studio(QObject):
    schema_changed = Signal(object)
    status_changed = Signal(str, str)
    progress = Signal(int, int)
    rendered = Signal(object)
    failed = Signal(str)
    install_progress = Signal(object)
    install_finished = Signal(str, str)
    notice = Signal(str)
    paths_changed = Signal()

    def __init__(
        self,
        paths: DataPaths,
        config: AppConfig,
        catalog: Catalog,
        store: Store,
        installer: Installer,
        supervisor: WorkerSupervisor,
        jobs: JobQueue,
    ) -> None:
        super().__init__()
        self.paths = paths
        self.config = config
        self.catalog = catalog
        self.store = store
        self.installer = installer
        self.supervisor = supervisor
        self.jobs = jobs
        self.engine_id = config.last_engine or "windows"
        self.lang = config.last_lang or "ko"
        self.voice = config.last_voice
        self.format = (
            config.default_format if config.default_format in {"wav", "flac", "ogg", "mp3"} else "wav"
        )
        self.srt = True
        self.schema: CapabilitySchema | None = None
        self._install: _InstallThread | None = None
        self._remove: _RemoveThread | None = None
        jobs.progress.connect(self.progress)
        jobs.finished.connect(self._on_rendered)
        jobs.failed.connect(self.failed)
        jobs.schema_ready.connect(self._on_schema)

    def engine_entries(self) -> list[EngineEntry | None]:
        return list(self.catalog.engines)

    def status_of(self, engine_id: str) -> str:
        return self.installer.status(engine_id)

    def select_engine(self, engine_id: str) -> None:
        switching = engine_id != self.engine_id
        self.engine_id = engine_id
        self.config.last_engine = engine_id
        if switching:
            self.lang = "ko"
            self.config.last_lang = self.lang
            self.voice = ""
            self.config.last_voice = ""
        status = self.installer.status(engine_id)
        if engine_id == "windows":
            status = "CHECKING"
        self.status_changed.emit(engine_id, status)
        if status == NOT_INSTALLED and engine_id != "windows":
            self.schema = None
            self.schema_changed.emit(None)
            return
        try:
            schema = static_schema(engine_id, self.paths, self.config.threads)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
            return
        self.schema = schema
        if switching and schema.languages and self.lang not in {lang.code for lang in schema.languages}:
            self.lang = schema.languages[0].code
            self.config.last_lang = self.lang
        self.voice = voice_for_lang(schema.voices, self.lang, self.voice if schema.voices else "")
        self.config.last_voice = self.voice
        self.jobs.remember_schema(engine_id, schema)
        self.schema_changed.emit(schema)
        self.jobs.refresh_schema(engine_id)

    def set_voice(self, voice: str) -> None:
        self.voice = voice
        self.config.last_voice = voice

    def set_lang(self, lang: str) -> None:
        self.lang = lang
        self.config.last_lang = lang
        if self.schema is not None:
            self.voice = voice_for_lang(self.schema.voices, lang, self.voice)
            self.config.last_voice = self.voice
            self.schema_changed.emit(self.schema)

    def preview_text(self, text: str) -> str:
        chunks = prepare(
            text,
            default_voice=self.voice or "F1",
            entries=self.store.list_dict(self.engine_id),
            normalize=self.config.normalize,
            acronyms=self.config.expand_acronyms,
            max_chars=self.schema.limits.max_chars_per_request if self.schema else 300,
        )
        return "\n".join(chunk.text for chunk in chunks)

    def detected(self, text: str) -> str:
        return detect_lang(text)

    def generate(self, text: str, params: dict[str, Any], *, preview: bool) -> None:
        if not text.strip():
            self.failed.emit("원고가 비어 있습니다.")
            return
        if self.installer.status(self.engine_id) == NOT_INSTALLED and self.engine_id != "windows":
            self.failed.emit("엔진을 먼저 설치하세요.")
            return
        voice = self.voice or (self.schema.voices[0].id if self.schema and self.schema.voices else "")
        if not voice:
            self.failed.emit("음성을 선택하세요.")
            return
        self.jobs.start(
            engine_id=self.engine_id,
            lang=self.lang,
            voice=voice,
            text=text,
            params=params,
            out_path=self.output_path(preview),
            normalize=self.config.normalize,
            acronyms=self.config.expand_acronyms,
            target_sr=self.config.sample_rate,
            lufs=self.config.lufs,
            write_srt=self.srt and not preview,
            preview=preview,
        )

    def output_path(self, preview: bool) -> Path:
        if preview:
            return self.paths.tmp / "preview.wav"
        folder = Path(self.config.output_dir) if self.config.output_dir else self.paths.output
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return folder / f"hantts-{stamp}.{self.format}"

    def stop(self) -> None:
        self.jobs.cancel()

    def start_install(self, engine_id: str, *, find_links: Path | None = None) -> None:
        if self._install is not None and self._install.isRunning():
            self.notice.emit("이미 설치가 진행 중입니다.")
            return
        entry = self.catalog.get(engine_id)
        if entry is not None:
            for lic in entry.licenses:
                if lic.requires_consent:
                    self.store.record_consent(engine_id, lic.name)
        thread = _InstallThread(self.installer, engine_id, find_links)
        thread.progressed.connect(self.install_progress)
        thread.succeeded.connect(self._install_ok)
        thread.failed.connect(self._install_bad)
        self._install = thread
        self.status_changed.emit(engine_id, "INSTALLING")
        thread.start()

    def cancel_install(self) -> None:
        if self._install is not None:
            self._install.cancel()

    def uninstall(self, engine_id: str) -> None:
        if self._remove is not None and self._remove.isRunning():
            self.notice.emit(self.tr("이미 제거가 진행 중입니다."))
            return
        self.notice.emit(self.tr("엔진을 제거하는 중입니다."))

        def _after_stop() -> None:
            self._start_remove(engine_id)

        self.supervisor.request_stop(engine_id, _after_stop)

    def _start_remove(self, engine_id: str) -> None:
        thread = _RemoveThread(self.installer, engine_id)
        thread.succeeded.connect(self._remove_ok)
        thread.failed.connect(self._remove_bad)
        self._remove = thread
        thread.start()

    def _remove_ok(self, engine_id: str) -> None:
        if self.engine_id == engine_id:
            self.select_engine("windows")
        self.status_changed.emit(engine_id, NOT_INSTALLED)
        self.notice.emit(self.tr("엔진을 제거했습니다."))

    def _remove_bad(self, engine_id: str, message: str) -> None:
        self.status_changed.emit(engine_id, self.installer.status(engine_id))
        self.failed.emit(self.tr("엔진을 제거하지 못했습니다: %1").replace("%1", message))

    def save_config(self) -> None:
        self.config.save(self.paths.config)

    def set_engines_dir(self, folder: str) -> bool:
        """엔진·모델·uv 캐시를 folder 에 두고, 이미 그 폴더에 있는 엔진을 사용한다."""
        default = self.config.resolved_data_dir()
        text = folder.strip()
        target = Path(text).expanduser() if text else default
        if not target.is_absolute():
            self.failed.emit(self.tr("엔진 폴더는 전체 경로로 지정하세요."))
            return False
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as e:
            self.failed.emit(self.tr("엔진 폴더를 쓸 수 없습니다: %1").replace("%1", str(e)))
            return False
        use_default = target.resolve() == default.resolve()
        self.config.engines_dir = "" if use_default else str(target)
        new_paths = DataPaths(default, None if use_default else target)
        new_paths.ensure()
        if new_paths.storage.resolve() != self.paths.storage.resolve():
            self.supervisor.shutdown_all()
            self.paths = new_paths
            self.installer.paths = new_paths
            self.supervisor.paths = new_paths
            self.jobs.paths = new_paths
            if self.engine_id:
                self.select_engine(self.engine_id)
            message = self.tr("엔진을 이 폴더에 설치하고 사용합니다: %1")
            self.notice.emit(message.replace("%1", str(new_paths.storage)))
        self.save_config()
        self.paths_changed.emit()
        return True

    def _on_schema(self, engine_id: str, schema: object) -> None:
        if engine_id != self.engine_id or not isinstance(schema, CapabilitySchema):
            return
        self.schema = schema
        self.voice = voice_for_lang(schema.voices, self.lang, self.voice)
        self.config.last_voice = self.voice
        self.schema_changed.emit(schema)
        if engine_id == "windows":
            korean = any("ko" in voice.langs for voice in schema.voices)
            self.status_changed.emit(engine_id, INSTALLED if korean else "NEEDS_VOICE")
        else:
            self.status_changed.emit(engine_id, self.installer.status(engine_id))

    def _on_rendered(self, rendered: object) -> None:
        self.rendered.emit(rendered)

    def _install_ok(self, engine_id: str) -> None:
        self.install_finished.emit(engine_id, "")
        self.status_changed.emit(engine_id, INSTALLED)
        if engine_id == self.engine_id:
            self.select_engine(engine_id)

    def _install_bad(self, engine_id: str, message: str) -> None:
        self.install_finished.emit(engine_id, message)
        self.status_changed.emit(engine_id, self.installer.status(engine_id))
        self.failed.emit(message)


def voice_for_lang(voices: tuple[VoiceSpec, ...] | list[VoiceSpec], lang: str, current: str) -> str:
    """현재 언어를 읽는 음성을 고른다. 영어 음성으로 한국어를 읽으면 무음이 된다."""

    def supports(voice: VoiceSpec) -> bool:
        if not voice.langs or "*" in voice.langs:
            return True
        return any(
            code == lang or lang.startswith(f"{code}-") or code.startswith(f"{lang}-") for code in voice.langs
        )

    chosen = next((voice for voice in voices if voice.id == current and supports(voice)), None)
    if chosen is None:
        chosen = next((voice for voice in voices if supports(voice)), None)
    if chosen is None and voices and current not in {voice.id for voice in voices}:
        chosen = voices[0]
    return chosen.id if chosen is not None else current


def static_schema(engine_id: str, paths: DataPaths, threads: int) -> CapabilitySchema:
    ctx = EngineContext(paths.models(engine_id), paths.voices(engine_id), threads)
    return get_adapter_class(engine_id)(ctx).describe_static()


def is_rendered(obj: object) -> Rendered | None:
    return obj if isinstance(obj, Rendered) else None


def is_progress(obj: object) -> ProgressEvent | None:
    return obj if isinstance(obj, ProgressEvent) else None
