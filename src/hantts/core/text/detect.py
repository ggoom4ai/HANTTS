"""거친 언어 감지 (docs/07_TEXT_FRONTEND.md §5)."""

from __future__ import annotations

import re

_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")


def detect_lang(text: str) -> str:
    """한글 음절 비율이 30%를 넘으면 ko, 아니면 라틴 문자가 있으면 en, 없으면 ko."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return "ko"
    hangul = len(_HANGUL.findall(text))
    if hangul / len(chars) > 0.3:
        return "ko"
    if _LATIN.search(text):
        return "en"
    return "ko"
