from __future__ import annotations

import json
from pathlib import Path

import pytest

from hantts.core.schema import CapabilitySchema, ParamValidationError, validate_params
from hantts.engines.base import EngineContext
from hantts.engines.windows import WindowsAdapter


def _schema() -> CapabilitySchema:
    return WindowsAdapter(EngineContext(Path("."), Path("."))).describe_static()


def test_roundtrip_json() -> None:
    s = _schema()
    again = CapabilitySchema.from_dict(json.loads(json.dumps(s.to_dict())))
    assert again == s


def test_defaults_filled() -> None:
    v = validate_params(_schema(), {})
    assert v["rate"] == 1.0 and v["backend"] == "onecore"


@pytest.mark.parametrize(
    "bad",
    [{"rate": 9}, {"backend": "nope"}, {"ssml_mode": "yes"}, {"unknown": 1}],
)
def test_invalid(bad: dict[str, object]) -> None:
    with pytest.raises(ParamValidationError):
        validate_params(_schema(), bad)


def test_windows_static_schema_imports_without_windows() -> None:
    """Windows 어댑터는 Windows 패키지 없이도 import·describe_static 가능해야 한다 (호스트/CI 안전)."""
    s = _schema()
    assert s.engine_id == "windows" and s.languages[0].code == "ko"
    v = validate_params(s, {"backend": "sapi", "sapi_rate": -3})
    assert v["sapi_rate"] == -3 and v["rate"] == 1.0
    with pytest.raises(ParamValidationError):
        validate_params(s, {"sapi_rate": 11})
