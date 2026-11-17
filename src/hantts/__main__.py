"""HanTTS Studio 진입점."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--worker" in args:
        from hantts.worker.main import main as worker_main

        i = args.index("--worker")
        engine = args[i + 1] if i + 1 < len(args) else "windows"
        rest = args[:i] + args[i + 2 :]
        return worker_main(["--engine", engine, *rest])

    from PySide6.QtCore import QLocale, QTranslator
    from PySide6.QtWidgets import QApplication

    from hantts.app.i18n import EnTranslator
    from hantts.app.icons import app_icon
    from hantts.app.main_window import MainWindow
    from hantts.app.studio import Studio
    from hantts.app.theme import apply
    from hantts.app.wizard import Wizard
    from hantts.core.audio.player import Player
    from hantts.core.catalog import load_catalog
    from hantts.core.config import AppConfig, open_paths
    from hantts.core.installer import Installer
    from hantts.core.jobs import JobQueue
    from hantts.core.paths import app_dir
    from hantts.core.store import Store
    from hantts.core.supervisor import WorkerSupervisor

    app = QApplication(sys.argv if argv is None else [sys.argv[0], *args])
    app.setApplicationName("HanTTS Studio")
    app.setOrganizationName("HanTTS")
    app.setWindowIcon(app_icon())
    cfg = AppConfig.load(_bootstrap_config())
    paths = open_paths(cfg)
    logging.basicConfig(
        filename=str(paths.logs / "host.log"),
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    apply(app, cfg.theme if cfg.theme in {"dark"} else "dark")
    if cfg.language == "en":
        translator: QTranslator = EnTranslator()
        app.installTranslator(translator)
        QLocale.setDefault(QLocale(QLocale.Language.English))
    catalog_path = app_dir() / "engines" / "catalog" / "catalog.json"
    catalog = load_catalog(catalog_path)
    store = Store(paths.db)
    installer = Installer(paths, catalog, worker_wheel=_worker_wheel())
    supervisor = WorkerSupervisor(paths, catalog, cfg)
    jobs = JobQueue(paths, cfg, store, supervisor)
    player = Player()
    studio = Studio(
        paths,
        cfg,
        catalog,
        store,
        installer,
        supervisor,
        jobs,
    )
    window = MainWindow(studio, player)
    if not cfg.wizard_done and "--install-engine" not in args:
        Wizard(studio, window).exec()
    window.show()
    engine = cfg.last_engine if catalog.get(cfg.last_engine) else "windows"
    studio.select_engine(engine)
    if "--install-engine" in args:
        i = args.index("--install-engine")
        target = args[i + 1] if i + 1 < len(args) else "supertonic"
        from hantts.app.install_dialog import InstallDialog

        InstallDialog(studio, target, window).exec()
    if "--import-pack" in args:
        i = args.index("--import-pack")
        if i + 1 < len(args):
            from hantts.app.install_dialog import InstallDialog

            InstallDialog(studio, "", window, pack=Path(args[i + 1])).exec()
    code = app.exec()
    player.close()
    supervisor.shutdown_all()
    studio.save_config()
    store.close()
    return int(code)


def _bootstrap_config() -> Path:
    from hantts.core.config import AppConfig
    from hantts.core.paths import DataPaths, default_data_dir

    root = default_data_dir()
    paths = DataPaths(root)
    if paths.config.exists():
        cfg = AppConfig.load(paths.config)
        return DataPaths(cfg.resolved_data_dir()).config
    return paths.config


def _worker_wheel() -> Path | None:
    from hantts.core.paths import app_dir

    wheels = app_dir() / "wheels"
    if not wheels.exists():
        wheels = app_dir() / "dist" / "wheels"
    found = sorted(wheels.glob("hantts_worker-*.whl")) if wheels.exists() else []
    return found[-1] if found else None


if __name__ == "__main__":
    raise SystemExit(main())
