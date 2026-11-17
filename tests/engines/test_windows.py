from __future__ import annotations

import sys

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.windows]


def test_windows_voice_module() -> None:
    if sys.platform != "win32":
        pytest.skip("Windows 전용")
    pytest.importorskip("winrt")
