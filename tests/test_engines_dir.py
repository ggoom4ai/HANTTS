from __future__ import annotations

import os
from pathlib import Path

from hantts.app.engine_manager_view import disk_bar_units
from hantts.core.config import AppConfig, open_paths
from hantts.core.paths import DataPaths


def test_light_defaults_cap_threads_and_idle() -> None:
    cfg = AppConfig()
    assert cfg.idle_minutes == 2
    assert cfg.threads == min(4, max(1, (os.cpu_count() or 2) - 1))
    assert AppConfig(threads=8, idle_minutes=10).threads == 8


def test_engines_root_keeps_config_in_data_dir(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "data", tmp_path / "big")
    paths.ensure()
    assert paths.config == tmp_path / "data" / "config.toml"
    assert paths.db == tmp_path / "data" / "hantts.db"
    assert paths.models("melo") == tmp_path / "big" / "models" / "melo"
    assert paths.engine_dir("melo") == tmp_path / "big" / "engines" / "melo"
    assert paths.voices("melo") == tmp_path / "big" / "voices" / "melo"
    assert paths.uv_cache == tmp_path / "big" / "uv-cache"
    assert paths.python.is_dir()
    assert paths.uv_cache.is_dir()


def test_disk_bar_stays_inside_signed_int() -> None:
    assert disk_bar_units(3_862_034_286) == 3_862_034_286 // 1_048_576
    assert disk_bar_units(0) == 1
    assert disk_bar_units(500) == 1


def test_empty_engines_dir_uses_data_root(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "data")
    assert paths.storage == paths.root
    assert paths.engine_dir("windows") == tmp_path / "data" / "engines" / "windows"


def test_config_roundtrip_opens_engines_dir(tmp_path: Path) -> None:
    cfg = AppConfig(data_dir=str(tmp_path / "data"), engines_dir=str(tmp_path / "big"))
    path = tmp_path / "data" / "config.toml"
    cfg.save(path)
    loaded = AppConfig.load(path)
    assert loaded.engines_dir == str(tmp_path / "big")
    opened = open_paths(loaded)
    assert opened.models("supertonic") == tmp_path / "big" / "models" / "supertonic"
    assert opened.config.parent == tmp_path / "data"
