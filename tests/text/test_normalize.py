from __future__ import annotations

from pathlib import Path

import pytest

from hantts.core.text.normalize_ko import normalize_ko

_CASES = Path(__file__).with_name("cases_normalize.tsv")

_SPEC = {
    "2026": "이천이십육",
    "3개": "세 개",
    "5명": "다섯 명",
    "2시": "두 시",
    "3분": "삼 분",
    "15층": "십오 층",
    "7번": "칠 번",
    "3.14": "삼 점 일사",
    "1/2": "이분의 일",
    "45%": "사십오 퍼센트",
    "2026-11-16": "이천이십육 년 십일 월 십육 일",
    "14:30": "열네 시 삼십 분",
    "₩15,000": "만 오천 원",
    "$20": "이십 달러",
    "010-1234-5678": "공일공 일이삼사 오육칠팔",
    "5km": "오 킬로미터",
    "5.5km": "오 점 오 킬로미터",
    "3~5개": "세 개에서 다섯 개",
    "10000": "만",
    "15000": "만오천",
}


def test_spec_literals() -> None:
    for src, expected in _SPEC.items():
        assert normalize_ko(src) == expected


def test_acronyms_optional() -> None:
    assert normalize_ko("AI") == "AI"
    assert normalize_ko("AI", acronyms=True) == "에이아이"


def test_tsv_has_two_hundred_rows() -> None:
    rows = [line.split("\t") for line in _CASES.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) >= 200
    for src, expected in rows:
        assert normalize_ko(src) == expected


@pytest.mark.parametrize(("src", "expected"), list(_SPEC.items()))
def test_each_spec(src: str, expected: str) -> None:
    assert normalize_ko(src) == expected
