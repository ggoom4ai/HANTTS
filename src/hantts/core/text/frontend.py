"""화자 태그 → 사전 → 정규화 → 분할 → 청크 (docs/07_TEXT_FRONTEND.md §1)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from hantts.core.store import DictEntry
from hantts.core.text.dictionary import apply_dictionary
from hantts.core.text.normalize_ko import normalize_ko
from hantts.core.text.splitter import chunk_spans, split_sentences

_TAG = re.compile(r"^\[([A-Za-z0-9_-]+)\]\s*")


@dataclass(slots=True, frozen=True)
class Chunk:
    text: str
    voice: str
    start: int
    end: int
    source: str


def parse_speakers(text: str, default_voice: str) -> list[tuple[str, str, int]]:
    """줄 앞 `[음성ID]` 를 화자 전환으로 읽는다. (voice, line, offset)."""
    out: list[tuple[str, str, int]] = []
    voice = default_voice
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        m = _TAG.match(body.strip())
        if m and body.strip().startswith("["):
            voice = m.group(1)
            stripped = body.strip()[m.end() :]
            lead = line.index(stripped) if stripped and stripped in line else len(line) - len(line.lstrip())
            out.append((voice, stripped, offset + lead))
        else:
            content = body.strip()
            if content:
                lead = len(line) - len(line.lstrip())
                out.append((voice, content, offset + lead))
        offset += len(line)
    return out


def prepare(
    text: str,
    *,
    default_voice: str,
    entries: list[DictEntry] | None = None,
    normalize: bool = True,
    acronyms: bool = False,
    max_chars: int = 300,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for voice, line, base in parse_speakers(text, default_voice):
        mapped = apply_dictionary(line, entries or [])
        spoken = normalize_ko(mapped, acronyms=acronyms) if normalize else mapped
        spans = chunk_spans(split_sentences(spoken), max_chars)
        # 정규화 이후 offset 은 변환문에 대한 것이다. 편집기 하이라이트용으로 원문 줄 범위를 유지한다.
        source_end = base + len(line)
        for span in spans:
            chunks.append(Chunk(span.text, voice, base, source_end, line))
    return chunks
