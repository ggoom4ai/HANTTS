"""MeloTTS 한국어 프런트엔드 (docs/14_MELO_ONNX.md §4).

MyShell MeloTTS(MIT)의 한국어 정규화·음소 변환을 torch 없이 옮겼다.
단어 분리는 kykim/bert-kor-base 어휘의 WordPiece 다.
"""

from hantts.engines.melo_frontend.korean import encode

__all__ = ["encode"]
