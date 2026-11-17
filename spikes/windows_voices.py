"""OneCore 음성 목록을 출력한다. 한국어 음성 유무를 마지막 줄에 적는다."""

from __future__ import annotations

import sys


def main() -> int:
    if sys.platform != "win32":
        print("windows only")
        return 2
    try:
        from winrt.windows.media.speechsynthesis import SpeechSynthesizer
    except ImportError:
        print("winrt speech package missing")
        return 2
    voices = SpeechSynthesizer.all_voices
    korean = False
    for voice in voices:
        lang = str(getattr(voice, "language", ""))
        print(f"{voice.display_name}\t{lang}\t{voice.id}")
        if lang.lower().startswith("ko"):
            korean = True
    print("korean_voice=" + ("yes" if korean else "no"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
