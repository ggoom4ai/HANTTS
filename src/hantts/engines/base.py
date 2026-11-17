"""엔진 어댑터 추상 클래스. 워커 휠에 포함 (numpy, soundfile, 표준 라이브러리만)."""

from __future__ import annotations

import abc
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from hantts.core.schema import CapabilitySchema, SynthRequest, SynthResult, validate_params


class EngineError(Exception):
    code = "ENGINE_ERROR"


class NotLoaded(EngineError):
    code = "NOT_LOADED"


class InvalidParams(EngineError):
    code = "INVALID_PARAMS"


class UnsupportedLanguage(EngineError):
    code = "UNSUPPORTED_LANGUAGE"


class VoiceNotFound(EngineError):
    code = "VOICE_NOT_FOUND"


class TextTooLong(EngineError):
    code = "TEXT_TOO_LONG"


class Cancelled(EngineError):
    code = "CANCELLED"


@dataclass(slots=True)
class EngineContext:
    models_dir: Path
    voices_dir: Path
    threads: int = 2
    _cancel: threading.Event = field(default_factory=threading.Event)

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def request_cancel(self) -> None:
        self._cancel.set()

    def reset_cancel(self) -> None:
        self._cancel.clear()


def write_wav(path: str | Path, audio: np.ndarray, sample_rate: int) -> float:
    """float32 mono 로 저장하고 길이(초)를 반환."""
    import soundfile as sf

    a = np.asarray(audio, dtype=np.float32).reshape(-1)
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    np.clip(a, -1.0, 1.0, out=a)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), a, sample_rate, subtype="FLOAT")
    return float(len(a)) / float(sample_rate)


class EngineAdapter(abc.ABC):
    engine_id: str = ""

    def __init__(self, ctx: EngineContext) -> None:
        self.ctx = ctx
        self._loaded = False
        self._schema: CapabilitySchema | None = None

    # ---- 계약 -------------------------------------------------------------
    @abc.abstractmethod
    def describe_static(self) -> CapabilitySchema:
        """모델 로드 없이 반환 가능한 스키마. 엔진 패키지 import 금지."""

    @abc.abstractmethod
    def _load(self) -> None:
        """엔진 import + 모델 로드. models_dir 에서만 로드."""

    @abc.abstractmethod
    def _synthesize(self, req: SynthRequest, params: dict[str, object]) -> tuple[np.ndarray, int]:
        """(float32 mono audio, sample_rate) 반환."""

    def describe(self) -> CapabilitySchema:
        """load 이후 동적 항목(화자 등)을 반영하려면 오버라이드."""
        return self.describe_static()

    def import_voice(self, path: str) -> dict[str, Any]:
        """사용자 음성 파일을 엔진 voices 디렉터리로 가져온다."""
        raise EngineError(f"{self.engine_id} does not support import_voice")

    def _take_word_timestamps(self) -> list[dict[str, object]] | None:
        """직전 _synthesize 의 단어 타임스탬프 [{"text","start","end"}]. 지원 엔진만 오버라이드."""
        return None

    # ---- 공통 처리 ----------------------------------------------------------
    def load(self) -> float:
        t = time.perf_counter()
        if not self._loaded:
            self._load()
            self._loaded = True
            self._schema = self.describe()
        return time.perf_counter() - t

    @property
    def schema(self) -> CapabilitySchema:
        if self._schema is None:
            self._schema = self.describe()
        return self._schema

    def synthesize(self, req: SynthRequest) -> SynthResult:
        if not self._loaded:
            raise NotLoaded("call load() first")
        schema = self.schema
        langs = {lang.code for lang in schema.languages}
        if req.lang not in langs:
            raise UnsupportedLanguage(f"{self.engine_id} does not support {req.lang!r}")
        if len(req.text) > schema.limits.max_chars_per_request:
            raise TextTooLong(f"{len(req.text)} > {schema.limits.max_chars_per_request}")
        try:
            params = validate_params(schema, req.params)
        except ValueError as e:
            raise InvalidParams(str(e)) from e

        self.ctx.reset_cancel()
        t = time.perf_counter()
        audio, sr = self._synthesize(req, params)
        if self.ctx.cancelled():
            raise Cancelled("cancelled")
        elapsed = time.perf_counter() - t
        duration = write_wav(req.out_path, audio, sr)
        return SynthResult(
            path=req.out_path,
            sample_rate=sr,
            duration=duration,
            elapsed=elapsed,
            rtf=elapsed / duration if duration > 0 else 0.0,
            word_timestamps=self._take_word_timestamps(),
        )


def get_adapter_class(engine_id: str) -> type[EngineAdapter]:
    """엔진 id → 어댑터 클래스 (지연 import 로 다른 엔진 의존성을 건드리지 않음)."""
    import importlib

    module_map = {
        "supertonic": ("hantts.engines.supertonic", "SupertonicAdapter"),
        "melo": ("hantts.engines.melo", "MeloAdapter"),
        "windows": ("hantts.engines.windows", "WindowsAdapter"),
    }
    mod_name, cls_name = module_map[engine_id]
    cls: type[EngineAdapter] = getattr(importlib.import_module(mod_name), cls_name)
    return cls
