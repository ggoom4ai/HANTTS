"""엔진 SDK 시그니처를 spikes/introspect-<engine>.json 에 남긴다.

패키지가 없으면 해당 키를 missing 으로 기록하고 종료 코드 0을 반환한다.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any


def _sig(obj: object, name: str) -> str | dict[str, str]:
    try:
        value = getattr(obj, name)
    except AttributeError:
        return "missing"
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        return "missing"


def _supertonic() -> dict[str, Any]:
    try:
        from supertonic import TTS
    except ImportError:
        return {"import": "missing"}
    return {
        "import": "supertonic.TTS",
        "TTS": str(inspect.signature(TTS)),
        "get_voice_style": _sig(TTS, "get_voice_style"),
        "synthesize": _sig(TTS, "synthesize"),
    }


def _melo() -> dict[str, Any]:
    try:
        from melo.api import TTS
    except ImportError:
        return {"import": "missing"}
    return {
        "import": "melo.api.TTS",
        "TTS": str(inspect.signature(TTS)),
        "tts_to_file": _sig(TTS, "tts_to_file"),
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1 or args[0] not in {"supertonic", "melo"}:
        print("usage: introspect.py supertonic|melo", file=sys.stderr)
        return 2
    engine = args[0]
    payload = _supertonic() if engine == "supertonic" else _melo()
    dest = Path(__file__).resolve().parent / f"introspect-{engine}.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
