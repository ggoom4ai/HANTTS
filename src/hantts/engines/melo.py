"""MeloTTS ONNX 어댑터 (docs/03_ENGINES.md §2, docs/14_MELO_ONNX.md).

합성은 `melotts_kr.onnx` 한 장이다. 언어는 한국어, 화자는 모델의 spk2id.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from hantts.core.schema import (
    CapabilitySchema,
    Choice,
    Features,
    LanguageSpec,
    Limits,
    ParamSpec,
    SynthRequest,
    VoiceSpec,
)
from hantts.engines.base import Cancelled, EngineAdapter, EngineError
from hantts.engines.melo_onnx import MeloOnnx


class MeloAdapter(EngineAdapter):
    engine_id = "melo"

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        self._onnx: MeloOnnx | None = None

    def describe_static(self) -> CapabilitySchema:
        return CapabilitySchema(
            engine_id="melo",
            display_name="MeloTTS",
            engine_version="KR",
            sample_rate=0,
            languages=(LanguageSpec("ko", "한국어", "official"),),
            voices=(VoiceSpec("KR", "KR", langs=("ko",), preview_text="안녕하세요. 반갑습니다."),),
            params=(
                ParamSpec(
                    "language",
                    "enum",
                    "언어 모델",
                    "KR",
                    choices=(Choice("KR", "한국어"),),
                    order=1,
                ),
                ParamSpec("speaker", "enum", "화자", "KR", choices=(Choice("KR", "KR"),), order=2),
                ParamSpec("speed", "float", "속도", 1.0, min=0.5, max=2.0, step=0.05, unit="x", order=10),
                ParamSpec(
                    "sdp_ratio",
                    "float",
                    "억양 다양성",
                    0.2,
                    "확률적 길이 예측 비율",
                    min=0.0,
                    max=1.0,
                    step=0.05,
                    group="advanced",
                    order=20,
                ),
                ParamSpec(
                    "noise_scale",
                    "float",
                    "음색 변화",
                    0.6,
                    "값이 클수록 매번 조금씩 다른 음색",
                    min=0.0,
                    max=1.5,
                    step=0.05,
                    group="advanced",
                    order=30,
                ),
                ParamSpec(
                    "noise_scale_w",
                    "float",
                    "길이 변화",
                    0.8,
                    min=0.0,
                    max=1.5,
                    step=0.05,
                    group="advanced",
                    order=40,
                ),
                ParamSpec(
                    "split_sentences",
                    "bool",
                    "엔진 내부 문장 분할",
                    False,
                    "앱이 이미 문장으로 나눠 보냅니다.",
                    group="advanced",
                    order=50,
                ),
            ),
            features=Features(builtin_normalization=False),
            limits=Limits(max_chars_per_request=300),
        )

    def describe(self) -> CapabilitySchema:
        schema = self.describe_static()
        if self._onnx is None:
            return schema
        voices = tuple(
            VoiceSpec(name, name, langs=("ko",), preview_text="안녕하세요. 반갑습니다.")
            for name in self._onnx.speakers
        )
        choices = tuple(Choice(voice.id, voice.label) for voice in voices)
        params = tuple(
            replace(param, choices=choices, default=choices[0].value) if param.key == "speaker" else param
            for param in schema.params
        )
        return replace(schema, sample_rate=self._onnx.sample_rate, voices=voices, params=params)

    def _load(self) -> None:
        model = self.ctx.models_dir / "melotts_kr.onnx"
        if not model.is_file():
            raise EngineError("MeloTTS ONNX 모델이 없습니다. 엔진을 설치하세요.")
        self._onnx = MeloOnnx(self.ctx.models_dir, self.ctx.threads)
        self._onnx.load()

    def _synthesize(self, req: SynthRequest, params: dict[str, object]) -> tuple[np.ndarray, int]:
        if self.ctx.cancelled():
            raise Cancelled("cancelled")
        if self._onnx is None:
            raise EngineError("MeloTTS ONNX 모델이 아직 로드되지 않았습니다.")
        speaker = req.voice or str(params.get("speaker") or "KR")
        return self._onnx.synthesize(req.text, speaker, params)
