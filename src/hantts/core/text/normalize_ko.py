"""한국어 읽기 정규화 (docs/07_TEXT_FRONTEND.md §2).

의존성 없이 규칙으로만 변환한다. 출력에는 숫자를 남기지 않으므로 단계는 순서대로 치환해도 안전하다.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data" / "counters.tsv"
_SINO = "영일이삼사오육칠팔구"
_SMALL = ("", "십", "백", "천")
_BIG = ("", "만", "억", "조", "경")
_NAT_ONES = ("", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉")
_NAT_TENS = ("", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔")
_DIGIT = {
    "0": "공",
    "1": "일",
    "2": "이",
    "3": "삼",
    "4": "사",
    "5": "오",
    "6": "육",
    "7": "칠",
    "8": "팔",
    "9": "구",
}
_UNITS: tuple[tuple[str, str], ...] = (
    ("km/h", "시속 킬로미터"),
    ("km", "킬로미터"),
    ("cm", "센티미터"),
    ("mm", "밀리미터"),
    ("kg", "킬로그램"),
    ("mg", "밀리그램"),
    ("ml", "밀리리터"),
    ("°C", "도"),
    ("℃", "도"),
    ("GB", "기가바이트"),
    ("MB", "메가바이트"),
    ("KB", "킬로바이트"),
    ("TB", "테라바이트"),
    ("m", "미터"),
    ("g", "그램"),
    ("L", "리터"),
)
_ACRONYMS = {
    "AI": "에이아이",
    "USB": "유에스비",
    "CPU": "씨피유",
    "GPU": "지피유",
    "TTS": "티티에스",
    "PDF": "피디에프",
    "URL": "유알엘",
    "OK": "오케이",
    "PC": "피씨",
    "TV": "티비",
}


def sino(n: int, *, spaced: bool = False) -> str:
    """한자어 수. spaced 이면 만/억 단위 사이에 공백."""
    if n < 0:
        return "마이너스 " + sino(-n, spaced=spaced)
    if n == 0:
        return "영"
    groups: list[str] = []
    big = 0
    x = n
    while x:
        g = x % 10000
        x //= 10000
        if g:
            unit = _BIG[big] if big < len(_BIG) else ""
            if unit == "만" and g == 1:
                groups.append(unit)
            else:
                groups.append(_four(g) + unit)
        big += 1
    ordered = list(reversed(groups))
    return " ".join(ordered) if spaced else "".join(ordered)


def _four(g: int) -> str:
    parts: list[str] = []
    for i in range(4):
        d = g % 10
        g //= 10
        if d == 0:
            continue
        unit = _SMALL[i]
        digit = "" if d == 1 and unit else _SINO[d]
        parts.append(digit + unit)
    return "".join(reversed(parts))


def native(n: int) -> str:
    """1–99 고유어(단위명사 앞). 그 밖은 한자어."""
    if n <= 0 or n >= 100:
        return sino(n)
    ten, one = divmod(n, 10)
    if ten == 2 and one == 0:
        return "스무"
    return _NAT_TENS[ten] + _NAT_ONES[one]


def _digits(text: str) -> str:
    return "".join(_DIGIT[c] for c in text if c.isdigit())


def _decimal_words(whole: str, frac: str) -> str:
    return f"{sino(int(whole))} 점 {''.join(_SINO[int(c)] for c in frac)}"


def _amount(token: str) -> int:
    return int(token.replace(",", ""))


@lru_cache(maxsize=1)
def _counters() -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    if _DATA.exists():
        for line in _DATA.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            word, kind = line.split("\t")
            rows.append((word, kind))
    rows.sort(key=lambda r: len(r[0]), reverse=True)
    return tuple(rows)


def _counter_alt() -> str:
    return "|".join(re.escape(w) for w, _ in _counters())


def _counter_kind(word: str) -> str:
    return next(k for w, k in _counters() if w == word)


def _read_count(n: int, word: str) -> str:
    kind = _counter_kind(word)
    spoken = native(n) if kind == "native" and 0 < n < 100 else sino(n)
    return f"{spoken} {word}"


def normalize_ko(text: str, *, acronyms: bool = False) -> str:
    """숫자·날짜·단위·기호를 한국어 읽기로 바꾼다."""
    s = text
    s = re.sub(
        r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)",
        lambda m: f"{sino(int(m[1]))} 년 {sino(int(m[2]))} 월 {sino(int(m[3]))} 일",
        s,
    )
    s = re.sub(
        r"(?<!\d)(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
        lambda m: f"{sino(int(m[1]))} 년 {sino(int(m[2]))} 월 {sino(int(m[3]))} 일",
        s,
    )
    s = re.sub(
        r"(?<!\d)(0\d{1,2})-(\d{3,4})-(\d{4})(?!\d)",
        lambda m: " ".join(_digits(g) for g in m.groups()),
        s,
    )
    s = re.sub(
        r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?(?!\d)",
        _time,
        s,
    )
    s = re.sub(r"[₩￦]\s*(\d{1,3}(?:,\d{3})+|\d+)", lambda m: f"{sino(_amount(m[1]), spaced=True)} 원", s)
    s = re.sub(r"\$\s*(\d{1,3}(?:,\d{3})+|\d+)", lambda m: f"{sino(_amount(m[1]), spaced=True)} 달러", s)
    s = re.sub(r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d+)\s*원", lambda m: f"{sino(_amount(m[1]), spaced=True)} 원", s)
    s = re.sub(
        r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d+)\s*달러", lambda m: f"{sino(_amount(m[1]), spaced=True)} 달러", s
    )
    s = re.sub(
        r"(?<!\d)(\d+(?:\.\d+)?)\s*%",
        lambda m: (_decimal_words(*m[1].split(".")) if "." in m[1] else sino(int(m[1]))) + " 퍼센트",
        s,
    )
    s = re.sub(
        r"(?<!\d)(\d+)\s*/\s*(\d+)(?!\d)",
        lambda m: f"{sino(int(m[2]))}분의 {sino(int(m[1]))}",
        s,
    )
    counters = _counter_alt()
    if counters:
        s = re.sub(
            rf"(?<!\d)(\d+)\s*[~～]\s*(\d+)\s*({counters})",
            lambda m: f"{_read_count(int(m[1]), m[3])}에서 {_read_count(int(m[2]), m[3])}",
            s,
        )
    s = re.sub(r"(?<!\d)(\d+)\s*[~～]\s*(\d+)(?!\d)", lambda m: f"{sino(int(m[1]))}에서 {sino(int(m[2]))}", s)
    unit_alt = "|".join(re.escape(u) for u, _ in _UNITS)
    names = {u: name for u, name in _UNITS}

    def _unit(m: re.Match[str]) -> str:
        raw_n, unit = m[1], m[2]
        spoken = _decimal_words(*raw_n.split(".")) if "." in raw_n else sino(int(raw_n))
        return f"{spoken} {names[unit]}"

    s = re.sub(rf"(?<!\d)(\d+(?:\.\d+)?)\s*({unit_alt})", _unit, s)
    s = re.sub(
        r"(?<!\d)(\d+)\.(\d+)(?!\d)",
        lambda m: _decimal_words(m[1], m[2]),
        s,
    )
    if counters:
        s = re.sub(rf"(?<!\d)(\d+)\s*({counters})", lambda m: _read_count(int(m[1]), m[2]), s)
    s = re.sub(
        r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d+)(?!\d)",
        lambda m: sino(_amount(m[1])),
        s,
    )
    s = s.replace("&", " 그리고 ").replace("+", " 플러스 ").replace("@", " 골뱅이 ")
    s = re.sub(r"[~～]", "에서", s)
    s = re.sub(r"[ \t]{2,}", " ", s).strip()
    if acronyms:
        for src, dst in sorted(_ACRONYMS.items(), key=lambda kv: len(kv[0]), reverse=True):
            s = re.sub(rf"(?<![A-Za-z]){src}(?![A-Za-z])", dst, s)
    return s


def _time(m: re.Match[str]) -> str:
    hour, minute, second = int(m[1]), int(m[2]), m[3]
    hour_word = "영" if hour == 0 else native(hour)
    parts = [f"{hour_word} 시"]
    if minute:
        parts.append(f"{sino(minute)} 분")
    if second and int(second):
        parts.append(f"{sino(int(second))} 초")
    return " ".join(parts)
