"""MeloTTS ONNX 백엔드 (docs/14_MELO_ONNX.md §4).

카탈로그가 받은 `melotts_kr.onnx` 를 ONNX Runtime 으로 실행한다.
v1 은 한국어만 다루고, BERT 특징은 0 으로 둔다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from hantts.engines.base import EngineError, UnsupportedLanguage, VoiceNotFound
from hantts.engines.melo_frontend.korean import encode

_ALIASES = {"tone": "tones", "tones": "tones", "language": "lang_ids", "lang_ids": "lang_ids"}


class MeloOnnx:
    def __init__(self, models: Path, threads: int) -> None:
        self.models = models
        self.threads = threads
        self.sample_rate = 44100
        self.add_blank = True
        self.speakers: dict[str, int] = {"KR": 0}
        self._symbol_to_id: dict[str, int] = {}
        self._lang_id = 4
        self._tone_start = 11
        self._vocab: set[str] = set()
        self._session: Any = None
        self._inputs: dict[str, Any] = {}
        self._output = "audio"

    def load(self) -> None:
        import onnxruntime as ort

        config_path = self.models / "melotts_kr_config.json"
        symbols_path = self.models / "symbols.json"
        vocab_path = self.models / "vocab.txt"
        model_path = self.models / "melotts_kr.onnx"
        missing = [
            path.name for path in (config_path, symbols_path, vocab_path, model_path) if not path.is_file()
        ]
        if missing:
            raise EngineError("MeloTTS ONNX 파일이 없습니다: " + ", ".join(missing))
        config = json.loads(config_path.read_text(encoding="utf-8"))
        symbols = json.loads(symbols_path.read_text(encoding="utf-8"))
        data = config.get("data") or {}
        self.sample_rate = int(data.get("sampling_rate") or 44100)
        self.add_blank = bool(data.get("add_blank", True))
        self.speakers = {str(k): int(v) for k, v in dict(data.get("spk2id") or {"KR": 0}).items()}
        self._symbol_to_id = _symbol_ids(config, symbols)
        lang_ids = symbols.get("language_id_map") or {}
        tone_starts = symbols.get("language_tone_start_map") or {}
        self._lang_id = int(lang_ids.get("KR", 4))
        self._tone_start = int(tone_starts.get("KR", 11))
        self._vocab = {
            line.strip() for line in vocab_path.read_text(encoding="utf-8").splitlines() if line.strip()
        }
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, self.threads)
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # 문장마다 입력 길이가 다르다. 메모리 패턴을 켜 두면 두 번째 문장에서 프로세스가 죽는다.
        options.enable_mem_pattern = False
        self._session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self._inputs = {item.name: item for item in self._session.get_inputs()}
        self._output = self._session.get_outputs()[0].name

    def synthesize(self, text: str, speaker: str, params: dict[str, object]) -> tuple[np.ndarray, int]:
        if self._session is None:
            raise EngineError("MeloTTS ONNX 모델이 아직 로드되지 않았습니다.")
        language = str(params.get("language") or "KR")
        if language != "KR":
            raise UnsupportedLanguage("MeloTTS ONNX 는 한국어만 지원합니다.")
        if speaker not in self.speakers:
            if "KR" in self.speakers:
                speaker = "KR"
            else:
                raise VoiceNotFound(f"화자가 없습니다: {speaker}")
        phones, tones, langs = encode(
            text,
            vocab=self._vocab,
            symbol_to_id=self._symbol_to_id,
            lang_id=self._lang_id,
            tone_start=self._tone_start,
            add_blank=self.add_blank,
        )
        width = int(phones.shape[1])
        speed = float(params.get("speed") or 1.0)  # type: ignore[arg-type]
        values = {
            "x": phones,
            "x_lengths": np.asarray([width], dtype=np.int64),
            "sid": np.asarray([self.speakers[speaker]], dtype=np.int64),
            "tones": tones,
            "lang_ids": langs,
            "bert": np.zeros((1, 1024, width), dtype=np.float32),
            "ja_bert": np.zeros((1, 768, width), dtype=np.float32),
            "noise_scale": float(params.get("noise_scale") or 0.6),  # type: ignore[arg-type]
            "length_scale": 1.0 / speed if speed else 1.0,
            "noise_scale_w": float(params.get("noise_scale_w") or 0.8),  # type: ignore[arg-type]
            "sdp_ratio": float(params.get("sdp_ratio") or 0.2),  # type: ignore[arg-type]
        }
        feeds = _feeds(self._inputs, values)
        audio = self._session.run([self._output], feeds)[0]
        wave = np.asarray(audio, dtype=np.float32).reshape(-1)
        return wave, self.sample_rate


def _symbol_ids(config: dict[str, Any], symbols: dict[str, Any]) -> dict[str, int]:
    """체크포인트에 구워진 음소 ID.

    임베딩 행 순서는 ``melotts_kr_config.json`` 의 ``symbols`` 다.
    한국어 자모와 문장 부호는 그 목록의 인덱스가 ID다.
    목록이 없으면 ``symbols.json`` 의 ``symbol_to_id`` 를 쓴다.
    """
    order = config.get("symbols")
    if isinstance(order, list) and order and all(isinstance(item, str) for item in order):
        return {item: index for index, item in enumerate(order)}
    return {str(key): int(value) for key, value in dict(symbols["symbol_to_id"]).items()}


def _feeds(inputs: dict[str, Any], values: dict[str, Any]) -> dict[str, np.ndarray]:
    feeds: dict[str, np.ndarray] = {}
    for name, meta in inputs.items():
        key = _ALIASES.get(name, name)
        value = values[key]
        if isinstance(value, float):
            dtype = np.float16 if "float16" in meta.type else np.float32
            feeds[name] = (
                np.asarray(value, dtype=dtype) if len(meta.shape) == 0 else np.asarray([value], dtype=dtype)
            )
        else:
            feeds[name] = np.asarray(value)
    return feeds
