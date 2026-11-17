from __future__ import annotations

from hantts.core.store import DictEntry
from hantts.core.text.dictionary import apply_dictionary


def _entry(pattern: str, replacement: str, *, regex: bool = False) -> DictEntry:
    return DictEntry(1, pattern, replacement, "global", "", regex, False, True)


def test_longest_literal_wins_and_does_not_chain() -> None:
    text = "한TTS 한"
    entries = [_entry("한", "일"), _entry("한TTS", "한티티에스")]
    assert apply_dictionary(text, entries) == "한티티에스 일"


def test_regex_skips_occupied_span() -> None:
    text = "ABC123"
    entries = [_entry("ABC", "에이비씨"), _entry(r"\d+", "숫자", regex=True)]
    assert apply_dictionary(text, entries) == "에이비씨숫자"
