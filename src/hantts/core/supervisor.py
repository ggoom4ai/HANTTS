"""QProcess 워커 수명주기 (docs/02_ARCHITECTURE.md §3, docs/06_IPC_PROTOCOL.md)."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from hantts.core.catalog import Catalog
from hantts.core.config import AppConfig
from hantts.core.paths import DataPaths

Callback = Callable[[dict[str, Any]], None]


@dataclass
class _Pending:
    method: str
    params: dict[str, Any]
    callback: Callback
    sent: bool = False


@dataclass
class _Worker:
    engine_id: str
    process: QProcess
    queue: list[_Pending] = field(default_factory=list)
    inflight: dict[int, _Pending] = field(default_factory=dict)
    buffer: str = ""
    ready: bool = False
    closing: bool = False
    restarts: int = 0
    next_id: int = 1
    last_used: float = 0.0
    log_path: Path | None = None


class WorkerSupervisor(QObject):
    """엔진별 워커를 지연 시작하고, 요청 id 로 응답을 돌려준다."""

    failed = Signal(str, str)
    ready = Signal(str)

    def __init__(
        self, paths: DataPaths, catalog: Catalog, config: AppConfig, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.paths = paths
        self.catalog = catalog
        self.config = config
        self._workers: dict[str, _Worker] = {}
        self._stopping: dict[str, _Worker] = {}
        self._ping = QTimer(self)
        self._ping.setInterval(30_000)
        self._ping.timeout.connect(self._on_ping)
        self._ping.start()
        self._reap = QTimer(self)
        self._reap.setInterval(60_000)
        self._reap.timeout.connect(self._on_reap)
        self._reap.start()

    def call(self, engine_id: str, method: str, params: dict[str, Any] | None, callback: Callback) -> None:
        worker = self._ensure(engine_id)
        worker.queue.append(_Pending(method, params or {}, callback))
        worker.last_used = _now()
        self._flush(worker)

    def cancel(self, engine_id: str) -> None:
        worker = self._workers.get(engine_id)
        if worker is None or not worker.ready:
            return
        self._send(worker, "cancel", {})

    def shutdown(self, engine_id: str) -> None:
        self.request_stop(engine_id, lambda: None)

    def request_stop(self, engine_id: str, done: Callable[[], None]) -> None:
        """프로세스를 끝내고, 파일 잠금이 풀린 뒤에 done 을 호출한다."""
        worker = self._workers.pop(engine_id, None)
        if worker is None or worker.process.state() == QProcess.ProcessState.NotRunning:
            done()
            return
        worker.closing = True
        called = False

        def _once(*_args: object) -> None:
            nonlocal called
            if called:
                return
            called = True
            self._stopping.pop(engine_id, None)
            done()

        worker.process.finished.connect(_once)
        self._stopping[engine_id] = worker
        if worker.process.state() == QProcess.ProcessState.NotRunning:
            _once()
            return
        worker.process.kill()

    def shutdown_all(self) -> None:
        for engine_id in list(self._workers):
            self.shutdown(engine_id)

    def running(self, engine_id: str) -> bool:
        worker = self._workers.get(engine_id)
        return bool(worker and worker.ready and worker.process.state() != QProcess.ProcessState.NotRunning)

    # ---- 기동 ----------------------------------------------------------
    def _ensure(self, engine_id: str) -> _Worker:
        current = self._workers.get(engine_id)
        if current and current.process.state() != QProcess.ProcessState.NotRunning:
            return current
        self._evict_if_needed(engine_id)
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        env = QProcessEnvironment.systemEnvironment()
        for key, value in self._env(engine_id).items():
            env.insert(key, value)
        proc.setProcessEnvironment(env)
        worker = _Worker(
            engine_id=engine_id, process=proc, log_path=self.paths.logs / f"worker-{engine_id}.log"
        )
        worker.last_used = _now()
        proc.readyReadStandardOutput.connect(lambda eid=engine_id: self._on_stdout(eid))
        proc.readyReadStandardError.connect(lambda eid=engine_id: self._on_stderr(eid))
        proc.finished.connect(lambda code, status, eid=engine_id: self._on_finished(eid, code))
        program, args = self._command(engine_id)
        proc.start(program, args)
        self._workers[engine_id] = worker
        return worker

    def _command(self, engine_id: str) -> tuple[str, list[str]]:
        models = self.paths.models(engine_id)
        voices = self.paths.voices(engine_id)
        models.mkdir(parents=True, exist_ok=True)
        voices.mkdir(parents=True, exist_ok=True)
        tail = [
            "--models-dir",
            str(models),
            "--voices-dir",
            str(voices),
            "--threads",
            str(self.config.threads),
        ]
        entry = self.catalog.get(engine_id)
        frozen = bool(getattr(sys, "frozen", False))
        if engine_id == "windows" and frozen:
            return sys.executable, ["--worker", "windows", *tail]
        if entry is not None and entry.runtime != "builtin":
            py = self.paths.venv_python(engine_id)
            if not py.exists():
                raise FileNotFoundError(f"엔진이 설치되지 않았습니다: {engine_id}")
            return str(py), ["-X", "utf8", "-m", "hantts.worker.main", "--engine", engine_id, *tail]
        return sys.executable, ["-X", "utf8", "-m", "hantts.worker.main", "--engine", engine_id, *tail]

    def _env(self, engine_id: str) -> dict[str, str]:
        extra: dict[str, str] = {}
        entry = self.catalog.get(engine_id)
        if entry is not None:
            extra.update(entry.worker_env)
        env = self.paths.worker_env(engine_id, extra)
        if not getattr(sys, "frozen", False):
            src = str(Path(__file__).resolve().parents[2])
            env["PYTHONPATH"] = src + (os_pathsep() + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        return env

    def _evict_if_needed(self, incoming: str) -> None:
        alive = [w for w in self._workers.values() if w.process.state() != QProcess.ProcessState.NotRunning]
        if len(alive) < self.config.max_workers:
            return
        idle = [w for w in alive if w.engine_id != incoming and not w.inflight and not w.queue]
        if not idle:
            return
        victim = min(idle, key=lambda w: w.last_used)
        self.shutdown(victim.engine_id)

    def _flush(self, worker: _Worker) -> None:
        if not worker.ready:
            return
        pending = [item for item in worker.queue if not item.sent]
        for item in pending:
            req_id = worker.next_id
            worker.next_id += 1
            worker.inflight[req_id] = item
            item.sent = True
            self._write(worker, {"id": req_id, "method": item.method, "params": item.params})
        worker.queue = [item for item in worker.queue if not item.sent]

    def _send(self, worker: _Worker, method: str, params: dict[str, Any]) -> None:
        req_id = worker.next_id
        worker.next_id += 1
        self._write(worker, {"id": req_id, "method": method, "params": params})

    def _write(self, worker: _Worker, msg: dict[str, Any]) -> None:
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        worker.process.write(line.encode("utf-8"))

    # ---- IO ------------------------------------------------------------
    def _on_stdout(self, engine_id: str) -> None:
        worker = self._workers.get(engine_id)
        if worker is None:
            return
        raw = worker.process.readAllStandardOutput().data()
        worker.buffer += bytes(raw).decode("utf-8", errors="replace")
        while "\n" in worker.buffer:
            line, worker.buffer = worker.buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                msg: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._handle(worker, msg)

    def _handle(self, worker: _Worker, msg: dict[str, Any]) -> None:
        if msg.get("event") == "ready":
            worker.ready = True
            worker.restarts = 0
            self.ready.emit(worker.engine_id)
            self._flush(worker)
            return
        req_id = msg.get("id")
        if isinstance(req_id, int) and req_id in worker.inflight and "event" not in msg:
            pending = worker.inflight.pop(req_id)
            worker.last_used = _now()
            pending.callback(msg)

    def _on_stderr(self, engine_id: str) -> None:
        worker = self._workers.get(engine_id)
        if worker is None or worker.log_path is None:
            return
        data = bytes(worker.process.readAllStandardError().data()).decode("utf-8", errors="replace")
        if not data:
            return
        worker.log_path.parent.mkdir(parents=True, exist_ok=True)
        with worker.log_path.open("a", encoding="utf-8") as fh:
            fh.write(data)

    def _on_finished(self, engine_id: str, code: int) -> None:
        worker = self._workers.get(engine_id)
        if worker is None or worker.closing:
            return
        error = {
            "id": None,
            "error": {"code": "ENGINE_ERROR", "message": f"워커가 종료되었습니다 ({code})", "data": {}},
        }
        for pending in list(worker.inflight.values()) + [p for p in worker.queue if not p.sent]:
            pending.callback(error)
        worker.inflight.clear()
        worker.queue.clear()
        worker.ready = False
        restarts = worker.restarts
        self._workers.pop(engine_id, None)
        if restarts >= 3:
            self.failed.emit(engine_id, "워커를 세 번 다시 시작했지만 복구하지 못했습니다.")
            return
        delay = int(1000 * (2**restarts))
        QTimer.singleShot(delay, lambda eid=engine_id, n=restarts + 1: self._restart(eid, n))

    def _restart(self, engine_id: str, restarts: int) -> None:
        try:
            revived = self._ensure(engine_id)
        except OSError as e:
            self.failed.emit(engine_id, str(e))
            return
        revived.restarts = restarts

    def _on_ping(self) -> None:
        for worker in self._workers.values():
            if worker.ready and not worker.closing:
                self._send(worker, "ping", {})

    def _on_reap(self) -> None:
        limit = self.config.idle_minutes * 60
        for engine_id, worker in list(self._workers.items()):
            if worker.inflight or worker.queue:
                continue
            if _now() - worker.last_used > limit:
                self.shutdown(engine_id)


def _now() -> float:
    import time

    return time.monotonic()


def os_pathsep() -> str:
    import os

    return os.pathsep
