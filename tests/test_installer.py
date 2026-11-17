from __future__ import annotations

import json
from pathlib import Path

import pytest

from hantts.core.catalog import load_catalog
from hantts.core.errors import InstallError
from hantts.core.installer import INSTALLED, NOT_INSTALLED, Installer
from hantts.core.paths import DataPaths


class _Runner:
    def __init__(self, fail_on: str = "") -> None:
        self.fail_on = fail_on
        self.calls: list[list[str]] = []

    def run(self, args: list[str], *, env: dict[str, str], on_line: object) -> int:
        del env, on_line
        self.calls.append(args)
        joined = " ".join(args)
        if self.fail_on and self.fail_on in joined:
            return 1
        if "venv" in args:
            root = Path(args[args.index("venv") + 1])
            py = root / "Scripts" / "python.exe"
            py.parent.mkdir(parents=True, exist_ok=True)
            py.write_text("", encoding="utf-8")
        return 0


def _catalog(tmp_path: Path, wheel: Path) -> tuple[object, Path]:
    lock = tmp_path / "lock.txt"
    lock.write_text("demo==1\n", encoding="utf-8")
    raw = {
        "schema_version": 1,
        "catalog_version": "t",
        "engines": [
            {
                "id": "demo",
                "display_name": "Demo",
                "version": "1",
                "runtime": "onnx",
                "python": "3.11",
                "approx_disk_mb": 0,
                "lock_file": "lock.txt",
                "assets": [],
                "licenses": [],
            }
        ],
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return load_catalog(path), wheel


def test_uninstall_removes_readonly_tree(tmp_path: Path) -> None:
    wheel = tmp_path / "worker.whl"
    wheel.write_bytes(b"wheel")
    catalog, wheel = _catalog(tmp_path, wheel)
    paths = DataPaths(tmp_path / "data")
    paths.ensure()
    locked = paths.engine_dir("demo") / "venv" / "Lib" / "site.py"
    locked.parent.mkdir(parents=True)
    locked.write_text("x", encoding="utf-8")
    locked.chmod(0o444)
    model = paths.models("demo") / "model.bin"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"m")
    installer = Installer(paths, catalog, uv=Path("uv"), worker_wheel=wheel)
    installer.uninstall("demo")
    assert not paths.engine_dir("demo").exists()
    assert not paths.models("demo").exists()


def test_install_commit_and_rollback(tmp_path: Path) -> None:
    wheel = tmp_path / "worker.whl"
    wheel.write_bytes(b"wheel")
    catalog, wheel = _catalog(tmp_path, wheel)
    paths = DataPaths(tmp_path / "data")
    paths.ensure()
    ok = _Runner()
    installer = Installer(
        paths, catalog, uv=Path("uv"), worker_wheel=wheel, runner=ok, verify=lambda e, py: None
    )
    leftover = paths.uv_cache / "wheel-copy"
    leftover.parent.mkdir(parents=True, exist_ok=True)
    leftover.write_text("cache", encoding="utf-8")
    leftover.chmod(0o444)
    installer.install("demo")
    assert installer.status("demo") == INSTALLED
    assert not leftover.exists()
    assert paths.uv_cache.is_dir()
    assert (paths.engine_dir("demo") / "venv" / "Scripts" / "python.exe").exists()
    assert not (paths.engine_dir("demo") / "venv.new").exists()

    bad = _Runner(fail_on="pip")
    paths2 = DataPaths(tmp_path / "data2")
    paths2.ensure()
    (paths2.engine_dir("demo") / "venv").mkdir(parents=True)
    (paths2.engine_dir("demo") / "venv" / "keep").write_text("old", encoding="utf-8")
    installer2 = Installer(
        paths2, catalog, uv=Path("uv"), worker_wheel=wheel, runner=bad, verify=lambda e, py: None
    )
    kept = paths2.uv_cache / "wheel-copy"
    kept.write_text("cache", encoding="utf-8")
    with pytest.raises(InstallError):
        installer2.install("demo")
    assert kept.read_text(encoding="utf-8") == "cache"
    assert (paths2.engine_dir("demo") / "venv" / "keep").read_text(encoding="utf-8") == "old"
    assert not (paths2.engine_dir("demo") / "venv.new").exists()
    assert installer2.status("demo") == NOT_INSTALLED
