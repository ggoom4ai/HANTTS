"""사용자 발음 사전 적용. 긴 항목 우선, 한 번에 치환해 연쇄를 막는다."""

from __future__ import annotations

import re

from hantts.core.store import DictEntry


def apply_dictionary(text: str, entries: list[DictEntry]) -> str:
    enabled = [e for e in entries if e.enabled and e.pattern]
    literals = sorted((e for e in enabled if not e.is_regex), key=lambda e: len(e.pattern), reverse=True)
    regexes = [e for e in enabled if e.is_regex]
    occupied: list[tuple[int, int]] = []
    replacements: list[tuple[int, int, str]] = []

    for entry in literals:
        flags = 0 if entry.case_sensitive else re.IGNORECASE
        for m in re.finditer(re.escape(entry.pattern), text, flags):
            if _free(occupied, m.start(), m.end()):
                occupied.append(m.span())
                replacements.append((m.start(), m.end(), entry.replacement))
    for entry in regexes:
        flags = 0 if entry.case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(entry.pattern, flags)
        except re.error:
            continue
        for m in pattern.finditer(text):
            if m.start() == m.end():
                continue
            if _free(occupied, m.start(), m.end()):
                occupied.append(m.span())
                replacements.append((m.start(), m.end(), entry.replacement))
    if not replacements:
        return text
    replacements.sort()
    out: list[str] = []
    cursor = 0
    for start, end, repl in replacements:
        out.append(text[cursor:start])
        out.append(repl)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def _free(occupied: list[tuple[int, int]], start: int, end: int) -> bool:
    return all(end <= a or start >= b for a, b in occupied)
