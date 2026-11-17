from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def test_supertonic_importable() -> None:
    models = Path("models/supertonic")
    if not (models / "onnx" / "text_encoder.onnx").exists():
        pytest.skip("Supertonic 모델이 설치되지 않았습니다.")
    import supertonic  # noqa: F401
