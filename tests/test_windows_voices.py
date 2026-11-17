from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QListWidget, QPushButton
from pytestqt.qtbot import QtBot

from hantts.app.engine_manager_view import EngineManagerView
from hantts.app.studio import Studio
from hantts.core.catalog import load_catalog
from hantts.core.config import AppConfig
from hantts.core.installer import Installer
from hantts.core.jobs import JobQueue
from hantts.core.paths import DataPaths
from hantts.core.schema import CapabilitySchema, LanguageSpec, VoiceSpec
from hantts.core.store import Store
from hantts.core.supervisor import WorkerSupervisor


def test_windows_voice_list_button_opens_dialog(qtbot: QtBot, tmp_path: Path) -> None:
    paths = DataPaths(tmp_path)
    paths.ensure()
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    config = AppConfig(wizard_done=True, threads=1, idle_minutes=60, last_engine="windows")
    store = Store(paths.db)
    installer = Installer(paths, catalog, uv=Path("uv"))
    supervisor = WorkerSupervisor(paths, catalog, config)
    jobs = JobQueue(paths, config, store, supervisor)
    studio = Studio(paths, config, catalog, store, installer, supervisor, jobs)
    view = EngineManagerView(studio)
    qtbot.addWidget(view)

    buttons = [button for button in view.findChildren(QPushButton) if button.text() == "음성 목록"]
    assert len(buttons) == 1
    buttons[0].click()

    dialogs = [dialog for dialog in view.findChildren(QDialog) if dialog.windowTitle() == "Windows 음성 목록"]
    assert len(dialogs) == 1
    studio.schema_changed.emit(
        CapabilitySchema(
            engine_id="windows",
            display_name="Windows 음성",
            engine_version="test",
            sample_rate=0,
            languages=(LanguageSpec("ko", "한국어"),),
            voices=(VoiceSpec("onecore:heami", "Microsoft Heami", langs=("ko",), gender="female"),),
            params=(),
        )
    )
    listing = dialogs[0].findChild(QListWidget)
    assert listing is not None
    assert listing.count() == 1
    assert "Heami" in listing.item(0).text()
    dialogs[0].close()
    supervisor.shutdown_all()
    store.close()
