"""한국어 정규화와 음소열. MeloTTS melo/text/korean.py (MIT) 에서 가져왔다."""

from __future__ import annotations

import re
from collections.abc import Callable

import numpy as np

from hantts.engines.base import EngineError
from hantts.engines.melo_frontend.wordpiece import tokenize

_PUNCT = {"!", "?", "…", ",", ".", "'", "-", "¿", "¡"}
_ETC = {"1+1": "원플러스원", "2+1": "투플러스원"}
_EN = {
    "KOREA": "코리아",
    "IDOL": "아이돌",
    "IT": "아이티",
    "IQ": "아이큐",
    "UP": "업",
    "DOWN": "다운",
    "PC": "피씨",
    "CCTV": "씨씨티비",
    "SNS": "에스엔에스",
    "AI": "에이아이",
    "CEO": "씨이오",
    **{
        ch: name
        for ch, name in zip(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            [
                "에이",
                "비",
                "씨",
                "디",
                "이",
                "에프",
                "지",
                "에이치",
                "아이",
                "제이",
                "케이",
                "엘",
                "엠",
                "엔",
                "오",
                "피",
                "큐",
                "알",
                "에스",
                "티",
                "유",
                "브이",
                "더블유",
                "엑스",
                "와이",
                "제트",
            ],
            strict=True,
        )
    },
}
_HAN = re.compile(r"[⺀-⺙⺛-⻳⼀-⿕々〇〡-〩〸-〺〻㐀-䶵一-鿃豈-鶴侮-頻並-龎]")
_LATIN = re.compile(r"([A-Za-z]+)")
_g2p: Callable[[str], str] | None = None


def normalize(text: str) -> str:
    cleaned = _HAN.sub("", text.strip())
    cleaned = _swap(cleaned, _ETC)
    cleaned = _LATIN.sub(lambda m: _EN.get(m.group(), m.group()), cleaned)
    return cleaned.lower()


def g2p(norm_text: str, vocab: set[str], to_phonemes: Callable[[str], str] | None = None) -> list[str]:
    phoneme = to_phonemes or korean_text_to_phonemes
    phones: list[str] = []
    groups: list[list[str]] = []
    for token in tokenize(norm_text, vocab):
        if token.startswith("#"):
            if not groups:
                groups.append([])
            groups[-1].append(token.replace("#", ""))
        else:
            groups.append([token])
    for group in groups:
        text = "".join(group)
        if text == "[UNK]":
            phones.append("_")
            continue
        if text in _PUNCT:
            phones.append(text)
            continue
        phones.extend(phoneme(text))
    return ["_", *phones, "_"]


def korean_text_to_phonemes(text: str) -> str:
    global _g2p
    if _g2p is None:
        engine = _g2p_engine()
        from jamo import hangul_to_jamo

        def convert(value: str) -> str:
            spoken = engine(normalize(value))
            return "".join(hangul_to_jamo(spoken))

        _g2p = convert
    return _g2p(text)


def _g2p_engine() -> Callable[[str], str]:
    """g2pkk 를 쓰되, pip 설치와 nltk 다운로드가 워커 stdin 을 가져가지 않게 한다."""
    import nltk

    download = nltk.download

    def quiet(name: str, *_args: object, **_kwargs: object) -> bool:
        return bool(download(name, quiet=True, raise_on_error=False))

    nltk.download = quiet
    try:
        from g2pkk.g2pkk import G2p
    finally:
        nltk.download = download

    def check_mecab(self: object) -> None:
        del self

    def get_mecab(self: object) -> object:
        del self
        import mecab

        return mecab.MeCab()

    G2p.check_mecab = check_mecab
    G2p.get_mecab = get_mecab
    engine: Callable[[str], str] = G2p()
    return engine


def encode(
    text: str,
    *,
    vocab: set[str],
    symbol_to_id: dict[str, int],
    lang_id: int,
    tone_start: int,
    add_blank: bool,
    to_phonemes: Callable[[str], str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    phones = g2p(normalize(text), vocab, to_phonemes)
    unk = symbol_to_id.get("UNK")
    ids: list[int] = []
    for phone in phones:
        if phone in symbol_to_id:
            ids.append(symbol_to_id[phone])
        elif unk is not None:
            ids.append(unk)
        else:
            raise EngineError(f"음소가 심볼 표에 없습니다: {phone}")
    tones = [tone_start] * len(ids)
    langs = [lang_id] * len(ids)
    if add_blank:
        ids = _intersperse(ids, 0)
        tones = _intersperse(tones, 0)
        langs = _intersperse(langs, 0)
    return (
        np.asarray([ids], dtype=np.int64),
        np.asarray([tones], dtype=np.int64),
        np.asarray([langs], dtype=np.int64),
    )


def _swap(text: str, table: dict[str, str]) -> str:
    if not any(key in text for key in table):
        return text
    pattern = re.compile("|".join(re.escape(key) for key in table))
    return pattern.sub(lambda m: table[m.group()], text)


def _intersperse(values: list[int], item: int) -> list[int]:
    result = [item] * (len(values) * 2 + 1)
    result[1::2] = values
    return result
