"""BERT BasicTokenizer + WordPiece. `#` 접두는 MeloTTS `g2p` 와 같게 유지한다.

한글은 한자처럼 음절로 자르지 않는다. 어절을 통째로 넘겨야 g2pkk 가 받침 연음 규칙을 적용한다.
"""

from __future__ import annotations

_UNK = "[UNK]"


def is_cjk(cp: int) -> bool:
    return (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0x20000 <= cp <= 0x2A6DF
        or 0x2A700 <= cp <= 0x2B73F
        or 0x2B740 <= cp <= 0x2B81F
        or 0x2B820 <= cp <= 0x2CEAF
        or 0xF900 <= cp <= 0xFAFF
        or 0x2F800 <= cp <= 0x2FA1F
    )


def basic_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            tokens.append("".join(buf))
            buf.clear()

    for ch in text:
        if ch.isspace():
            flush()
        elif is_cjk(ord(ch)) or _is_punct(ch):
            flush()
            tokens.append(ch)
        else:
            buf.append(ch)
    flush()
    return tokens


def wordpiece(token: str, vocab: set[str], *, max_chars: int = 100) -> list[str]:
    if token in vocab:
        return [token]
    if len(token) > max_chars:
        return [_UNK]
    start = 0
    pieces: list[str] = []
    chars = list(token)
    while start < len(chars):
        end = len(chars)
        found: str | None = None
        while start < end:
            piece = "".join(chars[start:end])
            if start > 0:
                piece = "##" + piece
            if piece in vocab:
                found = piece
                break
            end -= 1
        if found is None:
            return [_UNK]
        pieces.append(found)
        start = end
    return pieces


def tokenize(text: str, vocab: set[str]) -> list[str]:
    out: list[str] = []
    for token in basic_tokens(text):
        out.extend(wordpiece(token, vocab))
    return out


def _is_punct(ch: str) -> bool:
    return ch in set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~…¿¡")
