from __future__ import annotations

from types import SimpleNamespace

from hantts.engines.melo_frontend.korean import encode, g2p
from hantts.engines.melo_frontend.wordpiece import tokenize
from hantts.engines.melo_onnx import _feeds, _symbol_ids


def test_hangul_word_stays_together() -> None:
    vocab = {"안녕", "하", "##세", "##요", "[UNK]"}
    assert tokenize("안녕 하세요", vocab) == ["안녕", "하", "##세", "##요"]


def test_wordpiece_keeps_hash_prefix() -> None:
    vocab = {"un", "##want", "[UNK]"}
    assert tokenize("unwant", vocab) == ["un", "##want"]


def test_g2p_wraps_phonemes() -> None:
    vocab = {"안녕"}
    seen: list[str] = []

    def phones(text: str) -> str:
        seen.append(text)
        return "ㄱ" if text else ""

    assert g2p("안녕", vocab, phones) == ["_", "ㄱ", "_"]
    assert seen == ["안녕"]


def test_encode_inserts_blanks() -> None:
    vocab = {"가"}
    symbols = {"_": 0, "ㄱ": 1, "UNK": 2}
    phones, tones, langs = encode(
        "가",
        vocab=vocab,
        symbol_to_id=symbols,
        lang_id=4,
        tone_start=11,
        add_blank=True,
        to_phonemes=lambda _text: "ㄱ",
    )
    assert list(phones[0]) == [0, 0, 0, 1, 0, 0, 0]
    assert tones[0, 1] == 11
    assert langs[0, 1] == 4


def test_symbol_ids_follow_checkpoint_order() -> None:
    # 원본 symbols.py 순서와 체크포인트 순서가 갈리면 체크포인트 인덱스를 쓴다.
    # '우리는'의 ㅇ을 원본 ID로 넣으면 체크포인트에서는 ㅅ으로 읽힌다.
    order = ["_", "æ", "ᄀ", "ᄋ", "UNK"]
    published = {"_": 0, "ᄀ": 1, "ᄋ": 2, "UNK": 3, "æ": 4}
    table = _symbol_ids({"symbols": order}, {"symbol_to_id": published})
    assert table["ᄋ"] == 3
    assert table["ᄀ"] == 2
    assert table["_"] == 0


def test_symbol_ids_fall_back_without_checkpoint_list() -> None:
    published = {"_": 0, "ᄀ": 1}
    assert _symbol_ids({}, {"symbol_to_id": published}) == published


def test_onnx_feeds_accept_scalar_or_vector() -> None:
    scalar = SimpleNamespace(type="tensor(float)", shape=[])
    vector = SimpleNamespace(type="tensor(float)", shape=[1])
    feeds = _feeds(
        {"noise_scale": scalar, "length_scale": vector},
        {"noise_scale": 0.6, "length_scale": 1.0},
    )
    assert feeds["noise_scale"].shape == ()
    assert feeds["length_scale"].shape == (1,)
