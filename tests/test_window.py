from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QCheckBox
from pytestqt.qtbot import QtBot

from hantts.app.install_dialog import InstallDialog
from hantts.app.main_window import MainWindow
from hantts.app.studio import Studio
from hantts.core.audio.player import Player
from hantts.core.catalog import load_catalog
from hantts.core.config import AppConfig
from hantts.core.installer import Installer
from hantts.core.jobs import JobQueue
from hantts.core.paths import DataPaths
from hantts.core.store import Store
from hantts.core.supervisor import WorkerSupervisor


def test_main_window_opens(qtbot: QtBot, tmp_path: Path) -> None:
    paths = DataPaths(tmp_path)
    paths.ensure()
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    config = AppConfig(wizard_done=True, threads=1, idle_minutes=60)
    store = Store(paths.db)
    installer = Installer(paths, catalog, uv=Path("uv"))
    supervisor = WorkerSupervisor(paths, catalog, config)
    jobs = JobQueue(paths, config, store, supervisor)
    studio = Studio(paths, config, catalog, store, installer, supervisor, jobs)
    player = Player()
    window = MainWindow(studio, player)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert not window.windowIcon().isNull()
    assert window.stack.count() == 5
    assert window.workspace.editor.toPlainText() == ""
    player.close()
    supervisor.shutdown_all()
    store.close()


def test_install_license_boxes_start_checked(qtbot: QtBot, tmp_path: Path) -> None:
    paths = DataPaths(tmp_path)
    paths.ensure()
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    config = AppConfig(wizard_done=True, threads=1, idle_minutes=60)
    store = Store(paths.db)
    installer = Installer(paths, catalog, uv=Path("uv"))
    supervisor = WorkerSupervisor(paths, catalog, config)
    jobs = JobQueue(paths, config, store, supervisor)
    studio = Studio(paths, config, catalog, store, installer, supervisor, jobs)

    def checked(engine_id: str) -> dict[str, bool]:
        dialog = InstallDialog(studio, engine_id)
        qtbot.addWidget(dialog)
        dialog._goto(1)
        boxes = {box.text(): box.isChecked() for box in dialog.findChildren(QCheckBox)}
        dialog.close()
        return boxes

    melo = checked("melo")
    assert melo["MIT (MeloTTS, gnyong 변환본)"] is True
    assert melo["kykim/bert-kor-base (BERT 사용 시, 라이선스 확인 필요)"] is True
    supertonic = checked("supertonic")
    assert supertonic["BigScience OpenRAIL-M (모델 가중치)"] is True
    assert supertonic["MIT (샘플 코드)"] is False
    supervisor.shutdown_all()
    store.close()


def test_engine_switch_keeps_only_the_script(qtbot: QtBot, tmp_path: Path) -> None:
    paths = DataPaths(tmp_path)
    paths.ensure()
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    config = AppConfig(wizard_done=True, threads=1, idle_minutes=60, last_lang="en", last_voice="old")
    store = Store(paths.db)
    installer = Installer(paths, catalog, uv=Path("uv"))
    supervisor = WorkerSupervisor(paths, catalog, config)
    jobs = JobQueue(paths, config, store, supervisor)
    studio = Studio(paths, config, catalog, store, installer, supervisor, jobs)
    player = Player()
    window = MainWindow(studio, player)
    qtbot.addWidget(window)
    work = window.workspace
    work.editor.setPlainText("원고는 남는다")
    studio.select_engine("windows")
    studio.set_lang("en")
    studio.set_voice("old-voice")
    work.panel.set_values({"rate": 1.4})
    work.wave.set_audio(np.ones(100, dtype=np.float32), sr=24000)
    work.progress_label.setText("완료")

    studio.select_engine("melo")
    studio.select_engine("windows")

    assert work.editor.toPlainText() == "원고는 남는다"
    assert studio.lang == "ko"
    assert studio.voice != "old-voice"
    assert work.panel.values()["rate"] == 1.0
    assert len(work.wave._peaks) == 0
    assert work.progress_label.text() == ""
    assert player.duration == 0
    player.close()
    supervisor.shutdown_all()
    store.close()
