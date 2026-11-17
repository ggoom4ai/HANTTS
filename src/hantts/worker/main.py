"""엔진 워커 진입점.

실행: python -X utf8 -m hantts.worker.main --engine windows --models-dir <dir> --voices-dir <dir> --threads 2
stdout = 프로토콜 전용, stderr = 로그.
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

from hantts.core.schema import SynthRequest
from hantts.engines.base import EngineAdapter, EngineContext, EngineError, get_adapter_class
from hantts.worker import protocol as P

log = logging.getLogger("hantts.worker")


_stdout_hold: list[object] = []


def _isolate_stdout() -> io.TextIOWrapper:
    """프로토콜 파이프를 따로 두고, fd 1 은 stderr 로 유지한다.

    sys.stdout 을 버리기만 하면 fd 1 이 닫힌다. 다음 문장에서 라이브러리가
    그 번호로 출력하면 워커 프로세스가 그대로 죽는다.
    """
    original = sys.stdout
    proto_fd = os.dup(original.fileno())
    os.dup2(sys.stderr.fileno(), original.fileno())
    _stdout_hold.append(original)
    sys.stdout = sys.stderr
    return io.TextIOWrapper(
        os.fdopen(proto_fd, "wb"), encoding="utf-8", newline="\n", write_through=True
    )


class Worker:
    def __init__(self, adapter: EngineAdapter, channel: P.Channel) -> None:
        self.adapter = adapter
        self.ch = channel
        self._busy = threading.Lock()

    def handle(self, msg: dict[str, Any]) -> bool:
        """True 를 반환하면 종료."""
        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        if method not in P.METHODS:
            self.ch.send(
                P.error(
                    req_id if isinstance(req_id, int) else None,
                    "INVALID_PARAMS",
                    f"unknown method {method!r}",
                )
            )
            return False
        if not isinstance(req_id, int):
            self.ch.send(P.error(None, "INVALID_PARAMS", "id must be int"))
            return False

        # cancel/ping 은 합성 중에도 즉시 처리 (stdin 리더 스레드에서 호출됨)
        if method == "ping":
            self.ch.send(P.result(req_id, {"pong": True}))
            return False
        if method == "cancel":
            self.adapter.ctx.request_cancel()
            self.ch.send(P.result(req_id, {"cancelled": True}))
            return False
        if method == "shutdown":
            self.ch.send(P.result(req_id, {}))
            return True

        threading.Thread(target=self._run, args=(req_id, method, params), daemon=True).start()
        return False

    def _run(self, req_id: int, method: str, params: dict[str, Any]) -> None:
        with self._busy:  # 엔진 호출은 직렬화
            try:
                self.ch.send(P.result(req_id, self._dispatch(method, params)))
            except EngineError as e:
                self.ch.send(P.error(req_id, e.code, str(e)))
            except MemoryError as e:
                self.ch.send(P.error(req_id, "OOM", str(e)))
            except Exception as e:  # noqa: BLE001 — 모든 예외를 프로토콜 오류로
                log.exception("engine error")
                self.ch.send(P.error(req_id, "ENGINE_ERROR", str(e), {"traceback": traceback.format_exc()}))

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        a = self.adapter
        if method == "describe":
            return a.describe().to_dict()
        if method == "load":
            return {"load_seconds": a.load()}
        if method == "synthesize":
            if not a._loaded:  # 편의: 자동 로드
                a.load()
            return a.synthesize(SynthRequest.from_dict(params)).to_dict()
        if method == "synthesize_batch":
            if not a._loaded:
                a.load()
            return {"items": [a.synthesize(SynthRequest.from_dict(p)).to_dict() for p in params["items"]]}
        if method == "list_voices":
            lang = params.get("lang")
            voices = [v for v in a.describe().voices if lang is None or "*" in v.langs or lang in v.langs]
            return {"voices": [_voice_dict(v) for v in voices]}
        if method == "import_voice":
            return a.import_voice(str(params.get("path") or ""))
        raise EngineError(f"method {method!r} not implemented by {a.engine_id}")


def _voice_dict(v: Any) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(v)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--models-dir", default=".")
    ap.add_argument("--voices-dir", default=".")
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args(argv)

    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    proto_out = _isolate_stdout()
    ch = P.Channel(proto_out)

    ctx = EngineContext(
        models_dir=Path(args.models_dir), voices_dir=Path(args.voices_dir), threads=args.threads
    )
    adapter = get_adapter_class(args.engine)(ctx)
    worker = Worker(adapter, ch)
    ch.send(P.event("ready", {"engine": args.engine, "worker_version": P.WORKER_VERSION, "pid": os.getpid()}))

    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = P.decode(line)
        except ValueError as e:
            ch.send(P.error(None, "INVALID_PARAMS", f"bad json: {e}"))
            continue
        if worker.handle(msg):
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
