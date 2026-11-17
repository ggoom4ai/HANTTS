"""NDJSON JSON-RPC 메시지 (docs/06_IPC_PROTOCOL.md). 표준 라이브러리만 사용."""

from __future__ import annotations

import json
from typing import IO, Any

WORKER_VERSION = "0.1.0"

METHODS = frozenset(
    {
        "ping",
        "describe",
        "load",
        "synthesize",
        "synthesize_batch",
        "cancel",
        "list_voices",
        "import_voice",
        "shutdown",
    }
)


def encode(msg: dict[str, Any]) -> str:
    return json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n"


def decode(line: str) -> dict[str, Any]:
    msg = json.loads(line)
    if not isinstance(msg, dict):
        raise ValueError("message must be an object")
    return msg


def result(req_id: int, data: dict[str, Any]) -> dict[str, Any]:
    return {"id": req_id, "result": data}


def error(req_id: int | None, code: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": req_id, "error": {"code": code, "message": message, "data": data or {}}}


def event(name: str, data: dict[str, Any], req_id: int | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"event": name, "data": data}
    if req_id is not None:
        msg["id"] = req_id
    return msg


class Channel:
    """프로토콜 전용 출력 채널. 스레드 안전하게 한 줄씩 기록."""

    def __init__(self, out: IO[str]) -> None:
        import threading

        self._out = out
        self._lock = threading.Lock()

    def send(self, msg: dict[str, Any]) -> None:
        with self._lock:
            self._out.write(encode(msg))
            self._out.flush()
