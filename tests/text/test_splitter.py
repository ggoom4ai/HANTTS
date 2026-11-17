from __future__ import annotations

from hantts.core.text.splitter import chunk_spans, split_sentences


def test_keeps_decimal_and_abbreviation() -> None:
    text = "Dr. Kim은 3.14를 말했다. 다음 문장이다."
    spans = split_sentences(text)
    assert spans[0].text.startswith("Dr. Kim은 3.14")
    assert "다음 문장이다." in spans[1].text


def test_does_not_split_url() -> None:
    text = "주소는 https://example.com/a.b 이다. 끝."
    spans = split_sentences(text)
    assert "https://example.com/a.b" in spans[0].text
    assert spans[1].text == "끝."


def test_merges_short_and_resplits() -> None:
    spans = split_sentences("네. 그리고 아주 긴 문장을 이어서 적습니다, 여기서 다시 나눕니다.")
    chunks = chunk_spans(spans, max_chars=20, min_chars=5)
    assert all(len(c.text) <= 24 for c in chunks)
    assert chunks[0].start >= 0
