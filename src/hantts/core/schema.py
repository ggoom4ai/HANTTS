"""Capability Schema — 호스트와 워커가 공유하는 계약 (docs/06_IPC_PROTOCOL.md).

워커 휠에 포함되므로 표준 라이브러리만 사용한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal

SCHEMA_VERSION = 1

ParamType = Literal["float", "int", "bool", "enum", "string", "file", "voice_blend"]
Group = Literal["basic", "advanced"]
KoreanSupport = Literal["official", "experimental", "none"]


@dataclass(slots=True, frozen=True)
class Choice:
    value: str
    label_ko: str
    label_en: str = ""


@dataclass(slots=True, frozen=True)
class ParamSpec:
    key: str
    type: ParamType
    label_ko: str
    default: Any = None
    help_ko: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str = ""
    choices: tuple[Choice, ...] = ()
    group: Group = "basic"
    order: int = 100
    visible_if: dict[str, Any] = field(default_factory=dict)
    file_filter: str = ""
    regex: str = ""


@dataclass(slots=True, frozen=True)
class LanguageSpec:
    code: str
    label_ko: str
    support: KoreanSupport | Literal["official"] = "official"


@dataclass(slots=True, frozen=True)
class VoiceSpec:
    id: str
    label: str
    langs: tuple[str, ...] = ("*",)
    gender: str = ""
    preview_text: str = ""
    license: str = ""


@dataclass(slots=True, frozen=True)
class Features:
    streaming: bool = False
    batch: bool = False
    phoneme_input: bool = False
    inline_pronunciation: bool = False
    voice_blend: bool = False
    custom_voice_import: bool = False
    word_timestamps: bool = False
    builtin_normalization: bool = False


@dataclass(slots=True, frozen=True)
class Limits:
    max_chars_per_request: int = 300
    ideal_chunk_seconds: tuple[float, float] = (2.0, 20.0)


@dataclass(slots=True, frozen=True)
class CapabilitySchema:
    engine_id: str
    display_name: str
    engine_version: str
    sample_rate: int
    languages: tuple[LanguageSpec, ...]
    voices: tuple[VoiceSpec, ...]
    params: tuple[ParamSpec, ...]
    features: Features = Features()
    limits: Limits = Limits()
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> CapabilitySchema:
        def params(p: dict[str, Any]) -> ParamSpec:
            p = dict(p)
            p["choices"] = tuple(Choice(**c) for c in p.get("choices", ()))
            return ParamSpec(**_known(ParamSpec, p))

        lim = dict(d.get("limits", {}))
        if "ideal_chunk_seconds" in lim:
            lim["ideal_chunk_seconds"] = tuple(lim["ideal_chunk_seconds"])
        return CapabilitySchema(
            engine_id=d["engine_id"],
            display_name=d["display_name"],
            engine_version=d["engine_version"],
            sample_rate=int(d["sample_rate"]),
            languages=tuple(LanguageSpec(**_known(LanguageSpec, x)) for x in d["languages"]),
            voices=tuple(
                VoiceSpec(**{**_known(VoiceSpec, v), "langs": tuple(v.get("langs", ("*",)))})
                for v in d["voices"]
            ),
            params=tuple(params(p) for p in d["params"]),
            features=Features(**_known(Features, d.get("features", {}))),
            limits=Limits(**_known(Limits, lim)),
            schema_version=int(d.get("schema_version", SCHEMA_VERSION)),
        )

    def param(self, key: str) -> ParamSpec | None:
        return next((p for p in self.params if p.key == key), None)


def _known(cls: type, d: dict[str, Any]) -> dict[str, Any]:
    """하위 호환: 모르는 필드는 버린다."""
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in names}


class ParamValidationError(ValueError):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"{key}: {message}")
        self.key = key


def validate_params(schema: CapabilitySchema, values: dict[str, Any]) -> dict[str, Any]:
    """값을 검증·정규화하고 기본값을 채운 dict 를 반환한다."""
    out: dict[str, Any] = {}
    for key in values:
        if schema.param(key) is None:
            raise ParamValidationError(key, "unknown parameter")
    for p in schema.params:
        v = values.get(p.key, p.default)
        if v is None:
            out[p.key] = None
            continue
        if p.type in ("float", "int"):
            try:
                v = float(v) if p.type == "float" else int(v)
            except (TypeError, ValueError) as e:
                raise ParamValidationError(p.key, "not a number") from e
            if p.min is not None and v < p.min:
                raise ParamValidationError(p.key, f"< {p.min}")
            if p.max is not None and v > p.max:
                raise ParamValidationError(p.key, f"> {p.max}")
        elif p.type == "bool":
            if not isinstance(v, bool):
                raise ParamValidationError(p.key, "not a bool")
        elif p.type == "enum" and p.choices and str(v) not in {c.value for c in p.choices}:
            raise ParamValidationError(p.key, f"invalid choice {v!r}")
        out[p.key] = v
    return out


@dataclass(slots=True)
class SynthRequest:
    text: str
    lang: str
    voice: str
    out_path: str
    params: dict[str, Any] = field(default_factory=dict)
    stream: bool = False
    seed: int | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> SynthRequest:
        return SynthRequest(**_known(SynthRequest, d))


@dataclass(slots=True)
class SynthResult:
    path: str
    sample_rate: int
    duration: float
    elapsed: float
    rtf: float
    word_timestamps: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
