from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QPushButton
from pytestqt.qtbot import QtBot

from hantts.app.pages import HistoryView
from hantts.app.studio import Studio
from hantts.core.audio.player import Player
from hantts.core.catalog import load_catalog
from hantts.core.config import AppConfig
from hantts.core.installer import Installer
from hantts.core.jobs import JobQueue
from hantts.core.paths import DataPaths
from hantts.core.store import Store
from hantts.core.supervisor import WorkerSupervisor


def test_history_delete_removes_the_selected_row(qtbot: QtBot, tmp_path: Path) -> None:
    paths = DataPaths(tmp_path)
    paths.ensure()
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    config = AppConfig(wizard_done=True, threads=1, idle_minutes=60)
    store = Store(paths.db)
    kept = store.add_history(
        engine_id="windows",
        voice="Heami",
        lang="ko",
        text="남겨 둘 문장입니다.",
        path=str(tmp_path / "keep.wav"),
        duration=1.2,
        params={},
    )
    gone = store.add_history(
        engine_id="melo",
        voice="KR",
        lang="ko",
        text="지울 문장입니다.",
        path=str(tmp_path / "gone.wav"),
        duration=2.0,
        params={},
    )
    installer = Installer(paths, catalog, uv=Path("uv"))
    supervisor = WorkerSupervisor(paths, catalog, config)
    jobs = JobQueue(paths, config, store, supervisor)
    studio = Studio(paths, config, catalog, store, installer, supervisor, jobs)
    player = Player()
    view = HistoryView(studio, player)
    qtbot.addWidget(view)
    view.show()

    assert view.list.count() == 2
    view.list.setCurrentRow(0)
    buttons = [button for button in view.findChildren(QPushButton) if button.text() == "선택삭제"]
    assert len(buttons) == 1
    buttons[0].click()

    left = store.list_history()
    assert [item.id for item in left] == [kept]
    assert gone not in {item.id for item in left}
    assert view.list.count() == 1
    player.close()
    supervisor.shutdown_all()
    store.close()


def test_history_delete_all_clears_every_row(qtbot: QtBot, tmp_path: Path) -> None:
    paths = DataPaths(tmp_path)
    paths.ensure()
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    config = AppConfig(wizard_done=True, threads=1, idle_minutes=60)
    store = Store(paths.db)
    store.add_history(
        engine_id="windows",
        voice="Heami",
        lang="ko",
        text="첫 문장입니다.",
        path=str(tmp_path / "a.wav"),
        duration=1.0,
        params={},
    )
    store.add_history(
        engine_id="melo",
        voice="KR",
        lang="ko",
        text="둘째 문장입니다.",
        path=str(tmp_path / "b.wav"),
        duration=1.5,
        params={},
    )
    installer = Installer(paths, catalog, uv=Path("uv"))
    supervisor = WorkerSupervisor(paths, catalog, config)
    jobs = JobQueue(paths, config, store, supervisor)
    studio = Studio(paths, config, catalog, store, installer, supervisor, jobs)
    player = Player()
    view = HistoryView(studio, player)
    qtbot.addWidget(view)
    view.show()

    def accept() -> None:
        box = view.findChild(QMessageBox)
        assert box is not None
        yes = box.button(QMessageBox.StandardButton.Yes)
        assert yes is not None
        yes.click()

    QTimer.singleShot(0, accept)
    clear = next(button for button in view.findChildren(QPushButton) if button.text() == "전체 삭제")
    clear.click()

    assert store.list_history() == []
    assert view.list.count() == 0
    player.close()
    supervisor.shutdown_all()
    store.close()
