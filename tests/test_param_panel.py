from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

from hantts.app.param_panel import ParamPanel
from hantts.engines.base import EngineContext
from hantts.engines.windows import WindowsAdapter


def test_rate_default_and_sapi_visibility(qtbot: QtBot) -> None:
    schema = WindowsAdapter(EngineContext(Path("."), Path("."))).describe_static()
    panel = ParamPanel()
    qtbot.addWidget(panel)
    panel.set_schema(schema, "windows")
    panel.show()
    assert panel.values()["rate"] == 1.0
    assert not panel._editors["sapi_rate"].isVisible()
    advanced = next(button for button in panel.findChildren(QPushButton) if button.text() == "고급")
    advanced.click()
    sapi = next(button for button in panel.findChildren(QPushButton) if button.text() == "SAPI 5")
    sapi.click()
    basic = next(button for button in panel.findChildren(QPushButton) if button.text() == "기본")
    basic.click()
    qtbot.waitUntil(lambda: panel._editors["sapi_rate"].isVisible())
    panel.reset()
    assert panel.values()["backend"] == "onecore"
    assert not panel._editors["sapi_rate"].isVisible()
