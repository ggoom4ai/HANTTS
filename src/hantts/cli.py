"""hantts-cli — GUI 와 같은 워커로 한 문장을 합성한다."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from hantts.core.paths import app_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hantts-cli", description="HanTTS 명령줄 합성")
    sub = parser.add_subparsers(dest="cmd", required=True)
    synth = sub.add_parser("synth", help="한 문장을 합성합니다")
    synth.add_argument("--engine", default="windows")
    synth.add_argument("--text", required=True)
    synth.add_argument("--lang", default="ko")
    synth.add_argument("--voice", default="")
    synth.add_argument("--out", required=True)
    synth.add_argument("--speed", type=float, default=None)
    sub.add_parser("engines", help="카탈로그 엔진 목록")
    args = parser.parse_args(argv)
    if args.cmd == "engines":
        return _engines()
    return _synth(args)


def _engines() -> int:
    catalog = app_dir() / "engines" / "catalog" / "catalog.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    for engine in data.get("engines", []):
        print(f"{engine['id']}\t{engine['display_name']}\t{engine.get('runtime')}")
    return 0


def _synth(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    models = out.parent / ".models"
    models.mkdir(exist_ok=True)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "hantts.worker.main",
            "--engine",
            args.engine,
            "--models-dir",
            str(models),
            "--voices-dir",
            str(models),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert proc.stdin and proc.stdout
    try:
        ready = json.loads(proc.stdout.readline())
        if ready.get("event") != "ready":
            print(ready, file=sys.stderr)
            return 1
        voice = args.voice or _first_voice(proc)
        params: dict[str, object] = {}
        if args.speed is not None:
            params["speed"] = args.speed
        reply = _call(
            proc,
            2,
            "synthesize",
            {
                "text": args.text,
                "lang": args.lang,
                "voice": voice,
                "out_path": str(out),
                "params": params,
            },
        )
        err = reply.get("error")
        if isinstance(err, dict):
            print(err.get("message"), file=sys.stderr)
            return 1
        result = reply.get("result")
        print(result["path"] if isinstance(result, dict) else "")
        _call(proc, 3, "shutdown", {})
        return 0
    finally:
        proc.kill()


def _first_voice(proc: subprocess.Popen[str]) -> str:
    schema = _call(proc, 1, "describe", {})
    result = schema.get("result")
    voices = result.get("voices") if isinstance(result, dict) else None
    if not isinstance(voices, list) or not voices:
        return ""
    first = voices[0]
    return str(first.get("id")) if isinstance(first, dict) else ""


def _call(
    proc: subprocess.Popen[str], req_id: int, method: str, params: dict[str, object]
) -> dict[str, Any]:
    assert proc.stdin and proc.stdout
    proc.stdin.write(
        json.dumps({"id": req_id, "method": method, "params": params}, ensure_ascii=False) + "\n"
    )
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            return {"error": {"message": "워커가 응답하지 않았습니다."}}
        msg = json.loads(line)
        if isinstance(msg, dict) and msg.get("id") == req_id and "event" not in msg:
            return msg


if __name__ == "__main__":
    raise SystemExit(main())
