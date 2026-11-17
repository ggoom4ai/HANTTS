"""Supertonic 3 어댑터 (docs/03_ENGINES.md §1).

합성 인자명은 supertonic 1.2+ SDK 기준이다.
`TTS.synthesize(text, voice_style, total_steps, speed, silence_duration, lang, verbose)`.
`text_normalization` 은 SDK 인자가 없어 호스트 정규화 토글로만 쓴다.
"""

from __future__ import annotations

import inspect
import os
import shutil
from dataclasses import replace
from pathlib import Path
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
from hantts.engines.base import EngineAdapter, VoiceNotFound

_LANGS: tuple[tuple[str, str], ...] = (
    ("ko", "한국어"),
    ("en", "영어"),
    ("ja", "일본어"),
    ("es", "스페인어"),
    ("fr", "프랑스어"),
    ("de", "독일어"),
    ("pt", "포르투갈어"),
    ("it", "이탈리아어"),
    ("ru", "러시아어"),
    ("ar", "아랍어"),
    ("hi", "힌디어"),
    ("vi", "베트남어"),
    ("tr", "터키어"),
    ("pl", "폴란드어"),
    ("nl", "네덜란드어"),
    ("sv", "스웨덴어"),
    ("da", "덴마크어"),
    ("fi", "핀란드어"),
    ("cs", "체코어"),
    ("el", "그리스어"),
    ("hu", "헝가리어"),
    ("ro", "루마니아어"),
    ("uk", "우크라이나어"),
    ("bg", "불가리아어"),
    ("hr", "크로아티아어"),
    ("sk", "슬로바키아어"),
    ("sl", "슬로베니아어"),
    ("et", "에스토니아어"),
    ("lt", "리투아니아어"),
    ("lv", "라트비아어"),
    ("id", "인도네시아어"),
    ("na", "언어 자동"),
)
_VOICES = tuple(f"{g}{i}" for g in ("F", "M") for i in range(1, 6))


def _preset(name: str) -> VoiceSpec:
    gender = "female" if name.startswith("F") else "male"
    return VoiceSpec(name, name, langs=("*",), gender=gender, preview_text="안녕하세요. 반갑습니다.")


class SupertonicAdapter(EngineAdapter):
    engine_id = "supertonic"

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        self._tts: Any = None

    def describe_static(self) -> CapabilitySchema:
        lang_choices = tuple(Choice(code, label) for code, label in _LANGS)
        return CapabilitySchema(
            engine_id="supertonic",
            display_name="Supertonic 3",
            engine_version="3",
            sample_rate=0,
            languages=tuple(
                LanguageSpec(code, label, "official" if code != "na" else "experimental")
                for code, label in _LANGS
            ),
            voices=tuple(_preset(name) for name in _VOICES),
            params=(
                ParamSpec("lang", "enum", "언어", "ko", choices=lang_choices, order=1),
                ParamSpec(
                    "speed",
                    "float",
                    "속도",
                    1.0,
                    "1.0이 기본이고, 한국어는 0.95 전후가 자연스럽습니다.",
                    min=0.7,
                    max=1.5,
                    step=0.05,
                    unit="x",
                    order=10,
                ),
                ParamSpec(
                    "total_steps",
                    "int",
                    "품질 스텝",
                    8,
                    "클수록 또렷하고 느립니다. SDK 기본값은 8입니다.",
                    min=1,
                    max=20,
                    step=1,
                    group="advanced",
                    order=20,
                ),
                ParamSpec(
                    "text_normalization",
                    "bool",
                    "엔진 내장 정규화",
                    True,
                    "켜면 앱의 숫자 읽기 변환을 건너뜁니다.",
                    order=30,
                ),
                ParamSpec(
                    "chunk_silence_ms",
                    "int",
                    "문장 사이 쉼",
                    300,
                    "청크 사이에 넣는 무음입니다.",
                    min=0,
                    max=2000,
                    step=50,
                    unit="ms",
                    order=40,
                ),
                ParamSpec(
                    "voice_style_file",
                    "file",
                    "음성 스타일",
                    None,
                    "Voice Builder 가 만든 JSON",
                    file_filter="JSON (*.json)",
                    group="advanced",
                    order=50,
                ),
            ),
            features=Features(batch=False, custom_voice_import=True, builtin_normalization=True),
            limits=Limits(max_chars_per_request=300, ideal_chunk_seconds=(2.0, 20.0)),
        )

    def describe(self) -> CapabilitySchema:
        schema = self.describe_static()
        if self._tts is None:
            return schema
        names = [str(n) for n in (getattr(self._tts, "voice_style_names", None) or _VOICES)]
        voices = [_preset(name) for name in names]
        for path in sorted(self.ctx.voices_dir.glob("*.json")):
            if path.stem not in names:
                voices.append(
                    VoiceSpec(path.stem, f"{path.stem} (가져옴)", langs=("*",), preview_text="안녕하세요")
                )
        sr = int(getattr(self._tts, "sample_rate", 0) or 0)
        version = str(getattr(self._tts, "__module__", "supertonic"))
        return replace(
            schema, sample_rate=sr or schema.sample_rate, voices=tuple(voices), engine_version=version
        )

    def import_voice(self, path: str) -> dict[str, Any]:
        src = Path(path)
        if not src.is_file() or src.suffix.lower() != ".json":
            raise VoiceNotFound("JSON 음성 스타일 파일을 선택하세요.")
        self.ctx.voices_dir.mkdir(parents=True, exist_ok=True)
        dest = self.ctx.voices_dir / src.name
        shutil.copyfile(src, dest)
        self._schema = None
        return {
            "id": dest.stem,
            "label": dest.stem,
            "langs": ["*"],
            "gender": "",
            "preview_text": "안녕하세요",
            "license": "",
        }

    def _load(self) -> None:
        os.environ["SUPERTONIC_INTRA_OP_THREADS"] = str(self.ctx.threads)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["SUPERTONIC_CACHE_DIR"] = str(self.ctx.models_dir)
        from supertonic import TTS

        kwargs: dict[str, Any] = {}
        params = inspect.signature(TTS).parameters
        if "model" in params:
            kwargs["model"] = "supertonic-3"
        if "model_dir" in params:
            kwargs["model_dir"] = str(self.ctx.models_dir)
        if "auto_download" in params:
            kwargs["auto_download"] = False
        if "intra_op_num_threads" in params:
            kwargs["intra_op_num_threads"] = self.ctx.threads
        if "inter_op_num_threads" in params:
            kwargs["inter_op_num_threads"] = 1
        self._tts = TTS(**kwargs)

    def _synthesize(self, req: SynthRequest, params: dict[str, object]) -> tuple[np.ndarray, int]:
        if self.ctx.cancelled():
            from hantts.engines.base import Cancelled

            raise Cancelled("cancelled")
        tts = self._tts
        style_file = params.get("voice_style_file")
        try:
            if style_file:
                style = tts.get_voice_style_from_path(str(style_file))
            else:
                getter = tts.get_voice_style
                if "voice_name" in inspect.signature(getter).parameters:
                    style = getter(voice_name=req.voice)
                else:
                    style = getter(req.voice)
        except (FileNotFoundError, ValueError, OSError) as e:
            raise VoiceNotFound(str(e)) from e
        call: dict[str, Any] = {"text": req.text, "voice_style": style}
        sig = inspect.signature(tts.synthesize).parameters
        lang = str(params.get("lang") or req.lang)
        if "lang" in sig:
            call["lang"] = lang
        if "speed" in sig:
            speed = params["speed"]
            call["speed"] = float(speed) if isinstance(speed, int | float) else 1.0
        if "total_steps" in sig:
            steps = params["total_steps"]
            call["total_steps"] = int(steps) if isinstance(steps, int | float) else 8
        if "silence_duration" in sig and params.get("chunk_silence_ms") is not None:
            gap = params["chunk_silence_ms"]
            call["silence_duration"] = float(gap) / 1000.0 if isinstance(gap, int | float) else 0.0
        if "verbose" in sig:
            call["verbose"] = False
        wav, _duration = tts.synthesize(**call)
        audio = np.asarray(wav, dtype=np.float32).reshape(-1)
        sr = int(getattr(tts, "sample_rate", 0) or 44100)
        return audio, sr
