from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from hantts.core.catalog import load_catalog
from hantts.core.config import AppConfig
from hantts.core.jobs import JobQueue, _Job
from hantts.core.paths import DataPaths
from hantts.core.store import Store
from hantts.core.supervisor import WorkerSupervisor
from hantts.core.text.frontend import Chunk


def _queue(
    qtbot: QtBot, tmp_path: Path
) -> tuple[JobQueue, WorkerSupervisor, Store, list[tuple[object, ...]]]:
    del qtbot
    paths = DataPaths(tmp_path)
    paths.ensure()
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    config = AppConfig(threads=1, idle_minutes=60)
    store = Store(paths.db)
    supervisor = WorkerSupervisor(paths, catalog, config)
    jobs = JobQueue(paths, config, store, supervisor)
    sent: list[tuple[object, ...]] = []

    def capture(engine_id: str, method: str, params: dict[str, object], callback: object) -> None:
        sent.append((engine_id, method, params, callback))

    supervisor.call = capture  # type: ignore[method-assign]
    chunks = (
        Chunk("첫째 문장.", "v", 0, 6, "첫째 문장."),
        Chunk("둘째 문장.", "v", 7, 13, "둘째 문장."),
    )
    jobs._job = _Job(
        "windows",
        "ko",
        "v",
        "첫째 문장. 둘째 문장.",
        {},
        tmp_path / "out.wav",
        False,
        False,
        24000,
        None,
        0,
        False,
        chunks=list(chunks),
        session=tmp_path,
    )
    return jobs, supervisor, store, sent


def test_worker_death_retries_the_same_sentence(qtbot: QtBot, tmp_path: Path) -> None:
    jobs, _supervisor, store, sent = _queue(qtbot, tmp_path)
    jobs._on_chunk({"error": {"message": "워커가 종료되었습니다 (1)"}})
    assert jobs._job is not None
    assert jobs._retry_pending is True
    jobs._resume("windows")
    assert sent
    assert sent[0][1] == "synthesize"
    params = sent[0][2]
    assert isinstance(params, dict)
    assert params["text"] == "첫째 문장."
    store.close()


def test_repeated_worker_death_stops_the_job(qtbot: QtBot, tmp_path: Path) -> None:
    jobs, _supervisor, store, _sent = _queue(qtbot, tmp_path)
    failed: list[str] = []
    jobs.failed.connect(failed.append)
    for _ in range(2):
        jobs._on_chunk({"error": {"message": "워커가 종료되었습니다 (1)"}})
        jobs._retry_pending = False
    jobs._on_chunk({"error": {"message": "워커가 종료되었습니다 (1)"}})
    assert jobs._job is None
    assert failed == ["워커가 종료되었습니다 (1)"]
    store.close()
