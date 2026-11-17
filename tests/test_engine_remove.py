from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

from hantts.app.engine_manager_view import EngineManagerView
from hantts.app.studio import Studio
from hantts.core.catalog import load_catalog
from hantts.core.config import AppConfig
from hantts.core.installer import NOT_INSTALLED, Installer
from hantts.core.jobs import JobQueue
from hantts.core.paths import DataPaths
from hantts.core.store import Store
from hantts.core.supervisor import WorkerSupervisor


def test_remove_button_deletes_the_engine(qtbot: QtBot, tmp_path: Path) -> None:
    paths = DataPaths(tmp_path)
    paths.ensure()
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    entry = catalog.require("melo")
    root = paths.engine_dir("melo")
    locked = root / "venv" / "Lib" / "site.py"
    locked.parent.mkdir(parents=True)
    locked.write_text("x", encoding="utf-8")
    locked.chmod(0o444)
    python = paths.venv_python("melo")
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("", encoding="utf-8")
    (root / "engine.json").write_text(
        json.dumps({"id": "melo", "version": entry.version, "state": "INSTALLED"}),
        encoding="utf-8",
    )
    model = paths.models("melo") / "melotts_kr.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"onnx")

    config = AppConfig(wizard_done=True, threads=1, idle_minutes=60, last_engine="windows")
    store = Store(paths.db)
    installer = Installer(paths, catalog, uv=Path("uv"))
    supervisor = WorkerSupervisor(paths, catalog, config)
    jobs = JobQueue(paths, config, store, supervisor)
    studio = Studio(paths, config, catalog, store, installer, supervisor, jobs)
    errors: list[str] = []
    studio.failed.connect(errors.append)
    view = EngineManagerView(studio)
    qtbot.addWidget(view)

    buttons = [button for button in view.findChildren(QPushButton) if button.text() == "제거"]
    assert len(buttons) == 1
    buttons[0].click()
    qtbot.waitUntil(lambda: not root.exists() and not model.exists(), timeout=5000)

    assert not errors
    assert installer.status("melo") == NOT_INSTALLED
    supervisor.shutdown_all()
    store.close()
