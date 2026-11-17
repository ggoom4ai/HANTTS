"""문장 분할과 청크화. 원문 offset 을 유지한다 (docs/07_TEXT_FRONTEND.md §3)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_END = re.compile(r"[.!?…]+[\"'”’)\]]*")
_ABBR = re.compile(r"(?:Mr|Mrs|Ms|Dr|e\.g|i\.e|vs|No)\.$", re.IGNORECASE)
_URL = re.compile(r"https?://\S+|[\w.+-]+@[\w.-]+")


@dataclass(slots=True, frozen=True)
class Span:
    text: str
    start: int
    end: int


def split_sentences(text: str) -> list[Span]:
    """종결부호·줄바꿈으로 나누고, 소수점·약어·URL 은 자르지 않는다."""
    protected = {m.span() for m in _URL.finditer(text)}
    spans: list[Span] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\n":
            _push(spans, text, start, i)
            start = i + 1
            i += 1
            continue
        m = _END.match(text, i)
        if (
            m
            and not _inside(protected, m.start())
            and not _decimal(text, m.start())
            and not _abbr(text, m.end())
        ):
            end = m.end()
            while end < n and text[end] == " ":
                end += 1
            _push(spans, text, start, end)
            start = end
            i = end
            continue
        i += 1
    _push(spans, text, start, n)
    return spans


def chunk_spans(spans: list[Span], max_chars: int, *, min_chars: int = 5) -> list[Span]:
    """짧은 문장은 다음 문장과 합치고, 한도를 넘는 문장은 쉼표·접속어에서 다시 나눈다."""
    merged = _merge_short(spans, min_chars)
    out: list[Span] = []
    for span in merged:
        if len(span.text) <= max_chars:
            out.append(span)
        else:
            out.extend(_resplit(span, max_chars))
    return out


def _push(spans: list[Span], text: str, start: int, end: int) -> None:
    chunk = text[start:end].strip()
    if not chunk:
        return
    lead = len(text[start:end]) - len(text[start:end].lstrip())
    trail = len(text[start:end]) - len(text[start:end].rstrip())
    spans.append(Span(chunk, start + lead, end - trail))


def _inside(spans: set[tuple[int, int]], index: int) -> bool:
    return any(a <= index < b for a, b in spans)


def _decimal(text: str, dot: int) -> bool:
    return (
        dot > 0
        and dot + 1 < len(text)
        and text[dot] == "."
        and text[dot - 1].isdigit()
        and text[dot + 1].isdigit()
    )


def _abbr(text: str, end: int) -> bool:
    window = text[max(0, end - 8) : end]
    return bool(_ABBR.search(window))


def _merge_short(spans: list[Span], min_chars: int) -> list[Span]:
    if not spans:
        return []
    out: list[Span] = []
    buf = spans[0]
    for nxt in spans[1:]:
        if len(buf.text) < min_chars:
            buf = Span(f"{buf.text} {nxt.text}", buf.start, nxt.end)
        else:
            out.append(buf)
            buf = nxt
    out.append(buf)
    return out


def _resplit(span: Span, max_chars: int) -> list[Span]:
    text = span.text
    parts: list[Span] = []
    cursor = 0
    while len(text) - cursor > max_chars:
        window = text[cursor : cursor + max_chars]
        cut = _cut_point(window)
        if cut <= 0:
            cut = max_chars
        piece = window[:cut].strip()
        if piece:
            abs_start = span.start + cursor + (len(window[:cut]) - len(window[:cut].lstrip()))
            parts.append(Span(piece, abs_start, abs_start + len(piece)))
        cursor += cut
        while cursor < len(text) and text[cursor] == " ":
            cursor += 1
    rest = text[cursor:].strip()
    if rest:
        abs_start = span.start + cursor + (len(text[cursor:]) - len(text[cursor:].lstrip()))
        parts.append(Span(rest, abs_start, abs_start + len(rest)))
    return parts or [span]


def _cut_point(window: str) -> int:
    for token in (" 그리고 ", " 하지만 ", " 그러나 ", ", ", "，"):
        idx = window.rfind(token)
        if idx > len(window) // 4:
            return idx + len(token)
    return window.rfind(" ")
