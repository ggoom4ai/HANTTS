"""엔진 설치 상태 머신과 파이프라인 (docs/04_ENGINE_MANAGER.md §1–2, §5)."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from hantts.core.catalog import Catalog, EngineEntry
from hantts.core.download import CancelToken, download_asset
from hantts.core.errors import CancelledError, InstallError
from hantts.core.paths import DataPaths, app_dir

NOT_INSTALLED = "NOT_INSTALLED"
INSTALLING = "INSTALLING"
VERIFYING = "VERIFYING"
INSTALLED = "INSTALLED"
UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
BROKEN = "BROKEN"
NEEDS_VOICE = "NEEDS_VOICE"
UNAVAILABLE = "UNAVAILABLE"

def _force_remove(func: Callable[..., None], path: str, _exc: object) -> None:
    """uv git 캐시는 읽기 전용이라 일반 삭제로는 남는다."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


_WEIGHTS = (
    ("precheck", 0.02),
    ("python", 0.08),
    ("venv", 0.02),
    ("packages", 0.40),
    ("assets", 0.40),
    ("post", 0.03),
    ("verify", 0.05),
)


class CommandRunner(Protocol):
    def run(self, args: list[str], *, env: dict[str, str], on_line: Callable[[str], None]) -> int: ...


class SubprocessRunner:
    def run(self, args: list[str], *, env: dict[str, str], on_line: Callable[[str], None]) -> int:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            on_line(line.rstrip("\n"))
        return int(proc.wait())


@dataclass(slots=True)
class ProgressEvent:
    step: str
    fraction: float
    message: str
    log: str = ""


ProgressFn = Callable[[ProgressEvent], None]
VerifyFn = Callable[[EngineEntry, Path], None]


@dataclass
class Installer:
    paths: DataPaths
    catalog: Catalog
    uv: Path | None = None
    worker_wheel: Path | None = None
    runner: CommandRunner = field(default_factory=SubprocessRunner)
    verify: VerifyFn | None = None

    def status(self, engine_id: str) -> str:
        entry = self.catalog.get(engine_id)
        if entry is None:
            return NOT_INSTALLED
        if entry.runtime == "builtin":
            return INSTALLED
        meta = self._read_meta(engine_id)
        if meta is None:
            return NOT_INSTALLED
        state = str(meta.get("state") or INSTALLED)
        if state == BROKEN:
            return BROKEN
        if str(meta.get("version") or "") != entry.version:
            return UPDATE_AVAILABLE
        venv_py = self.paths.venv_python(engine_id)
        if not venv_py.exists():
            return BROKEN
        return INSTALLED

    def mark_broken(self, engine_id: str) -> None:
        meta = self._read_meta(engine_id) or {"id": engine_id}
        meta["state"] = BROKEN
        self._write_meta(engine_id, meta)

    def install(
        self,
        engine_id: str,
        *,
        on_progress: ProgressFn | None = None,
        cancel: CancelToken | None = None,
        find_links: Path | None = None,
    ) -> None:
        entry = self.catalog.require(engine_id)
        if entry.runtime == "builtin":
            raise InstallError("Windows 음성은 별도 설치가 없습니다.")
        token = cancel or CancelToken()
        done = 0.0

        def report(step: str, message: str, extra: float = 0.0, log: str = "") -> None:
            weight = dict(_WEIGHTS)[step]
            if on_progress:
                on_progress(ProgressEvent(step, min(1.0, done + weight * extra), message, log))

        try:
            self._precheck(entry)
            report("precheck", "디스크와 경로를 확인했습니다.", 1)
            done += 0.02
            token.raise_if_cancelled()
            self._python(entry, token, report)
            done += 0.08
            token.raise_if_cancelled()
            py = self._venv(entry, token, report)
            done += 0.02
            token.raise_if_cancelled()
            self._packages(entry, py, token, report, find_links)
            done += 0.40
            token.raise_if_cancelled()
            self._assets(entry, token, report)
            done += 0.40
            token.raise_if_cancelled()
            self._post(entry, py, token, report)
            done += 0.03
            token.raise_if_cancelled()
            report("verify", "검증 합성을 준비합니다.", 0.2)
            if self.verify is not None:
                self.verify(entry, py)
            report("verify", "검증을 마쳤습니다.", 1)
            self._commit(entry)
            with contextlib.suppress(OSError):
                self.clear_cache()
            if on_progress:
                on_progress(ProgressEvent("commit", 1.0, "설치가 완료되었습니다."))
        except CancelledError:
            self._rollback(engine_id)
            raise
        except Exception:
            self._rollback(engine_id)
            raise

    def uninstall(self, engine_id: str, *, keep_voices: bool = False) -> None:
        self._rollback(engine_id)
        targets = [self.paths.engine_dir(engine_id), self.paths.models(engine_id)]
        if not keep_voices:
            targets.append(self.paths.voices(engine_id))
        for path in targets:
            if not path.exists():
                continue
            try:
                shutil.rmtree(path, onerror=_force_remove)
            except OSError as e:
                raise InstallError(f"엔진 파일을 지우지 못했습니다: {path} ({e})") from e
        left = [str(path) for path in targets if path.exists()]
        if left:
            raise InstallError("엔진 파일을 지우지 못했습니다: " + ", ".join(left))

    def install_pack(
        self, pack: Path, *, on_progress: ProgressFn | None = None, cancel: CancelToken | None = None
    ) -> None:
        import zipfile

        if not zipfile.is_zipfile(pack):
            raise InstallError("엔진 팩(.htpack)이 아닙니다.")
        dest = self.paths.tmp / "pack"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        with zipfile.ZipFile(pack) as zf:
            zf.extractall(dest)
        meta_path = dest / "pack.json"
        if not meta_path.exists():
            raise InstallError("pack.json 이 없습니다.")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        engine_id = str(meta["engine_id"])
        self.install(engine_id, on_progress=on_progress, cancel=cancel, find_links=dest / "wheels")

    def cache_bytes(self) -> int:
        return (
            _dir_size(self.paths.uv_cache)
            + _dir_size(self.paths.storage / "models")
            + _dir_size(self.paths.storage / "engines")
        )

    def clear_cache(self) -> None:
        if self.paths.uv_cache.exists():
            shutil.rmtree(self.paths.uv_cache, onerror=_force_remove)
        self.paths.uv_cache.mkdir(parents=True, exist_ok=True)

    # ---- 단계 ----------------------------------------------------------
    def _precheck(self, entry: EngineEntry) -> None:
        target = self.paths.storage if self.paths.storage.exists() else Path.home()
        usage = shutil.disk_usage(target)
        need = int(entry.approx_disk_mb * 1.3 * 1024 * 1024)
        if usage.free < need:
            raise InstallError(f"디스크 여유가 부족합니다. 약 {entry.approx_disk_mb}MB 가 필요합니다.")
        probe = self.paths.storage / ".write_probe"
        try:
            probe.write_text("ok", encoding="utf-8")
        except OSError as e:
            raise InstallError("엔진 폴더에 쓸 수 없습니다.") from e
        else:
            probe.unlink(missing_ok=True)
        if not entry.assets:
            return
        missing = [a.dest for a in entry.assets if not a.verified]
        if missing:
            raise InstallError("모델 파일의 SHA256 이 아직 없습니다: " + ", ".join(missing))

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["UV_CACHE_DIR"] = str(self.paths.uv_cache)
        env["UV_PYTHON_INSTALL_DIR"] = str(self.paths.python)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _uv(self) -> Path:
        if self.uv is not None:
            return self.uv
        bundled = app_dir() / "uv.exe"
        if bundled.exists():
            return bundled
        found = shutil.which("uv")
        if not found:
            raise InstallError("uv.exe 를 찾지 못했습니다. 앱 폴더 또는 PATH 를 확인하세요.")
        return Path(found)

    def _python(self, entry: EngineEntry, cancel: CancelToken, report: Callable[..., None]) -> None:
        if not entry.python:
            return
        report("python", f"Python {entry.python} 을 준비합니다.")
        code = self.runner.run(
            [str(self._uv()), "python", "install", entry.python],
            env=self._env(),
            on_line=lambda line: report("python", line, log=line),
        )
        cancel.raise_if_cancelled()
        if code != 0:
            raise InstallError(f"Python {entry.python} 설치에 실패했습니다.")

    def _venv(self, entry: EngineEntry, cancel: CancelToken, report: Callable[..., None]) -> Path:
        report("venv", "가상환경을 만듭니다.")
        new = self.paths.engine_dir(entry.id) / "venv.new"
        if new.exists():
            shutil.rmtree(new)
        new.parent.mkdir(parents=True, exist_ok=True)
        args = [str(self._uv()), "venv", str(new)]
        if entry.python:
            args.extend(["--python", entry.python])
        code = self.runner.run(args, env=self._env(), on_line=lambda line: report("venv", line, log=line))
        cancel.raise_if_cancelled()
        if code != 0:
            raise InstallError("가상환경 생성에 실패했습니다.")
        py = new / "Scripts" / "python.exe"
        if not py.exists():
            raise InstallError("venv 안의 python.exe 가 없습니다.")
        return py

    def _packages(
        self,
        entry: EngineEntry,
        py: Path,
        cancel: CancelToken,
        report: Callable[..., None],
        find_links: Path | None,
    ) -> None:
        report("packages", "패키지를 설치합니다.")
        lock = (self.catalog.path.parent / entry.lock_file) if entry.lock_file else None
        args = [str(self._uv()), "pip", "install", "--python", str(py)]
        for url in entry.extra_index_urls:
            args.extend(["--extra-index-url", url])
        if find_links is not None:
            args.extend(["--no-index", "--find-links", str(find_links)])
        if lock is not None and lock.exists():
            args.extend(["-r", str(lock)])
        if self.worker_wheel is not None and self.worker_wheel.exists():
            args.append(str(self.worker_wheel))
        has_req = (lock is not None and lock.exists()) or find_links is not None
        has_wheel = self.worker_wheel is not None and self.worker_wheel.exists()
        if not has_req and not has_wheel:
            raise InstallError("잠금 파일이 없습니다.")
        code = self.runner.run(
            args, env=self._env(), on_line=lambda line: report("packages", line, 0.5, line)
        )
        cancel.raise_if_cancelled()
        if code != 0:
            raise InstallError("패키지 설치에 실패했습니다.")

    def _assets(self, entry: EngineEntry, cancel: CancelToken, report: Callable[..., None]) -> None:
        if not entry.assets:
            report("assets", "받을 모델 파일이 없습니다.", 1)
            return
        root = self.paths.models(entry.id)
        total = len(entry.assets)
        for i, asset in enumerate(entry.assets):
            dest = root / asset.dest

            def on_bytes(
                done: int,
                size: int,
                speed: float,
                eta: float | None,
                *,
                index: int = i,
                name: str = asset.dest,
            ) -> None:
                frac = (index + (done / size if size else 1)) / total
                report("assets", f"{name} · {speed / 1_048_576:.1f} MB/s", frac)

            download_asset(asset, dest, cancel=cancel, on_progress=on_bytes)
        report("assets", "모델 파일을 확인했습니다.", 1)

    def _post(self, entry: EngineEntry, py: Path, cancel: CancelToken, report: Callable[..., None]) -> None:
        if not entry.post_install:
            report("post", "후처리 단계가 없습니다.", 1)
            return
        env = self._env()
        env.update(self.paths.worker_env(entry.id, entry.worker_env))
        env.pop("HF_HUB_OFFLINE", None)
        env.pop("TRANSFORMERS_OFFLINE", None)
        for step in entry.post_install:
            if step.type != "python" or not step.module:
                continue
            report("post", step.module)
            code = self.runner.run(
                [str(py), "-m", step.module, *step.args],
                env=env,
                on_line=lambda line: report("post", line, log=line),
            )
            cancel.raise_if_cancelled()
            if code != 0:
                raise InstallError(f"후처리에 실패했습니다: {step.module}")

    def _commit(self, entry: EngineEntry) -> None:
        root = self.paths.engine_dir(entry.id)
        new = root / "venv.new"
        target = root / "venv"
        backup = root / "venv.bak"
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        if target.exists():
            target.rename(backup)
        new.rename(target)
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        self._write_meta(
            entry.id,
            {
                "id": entry.id,
                "version": entry.version,
                "installed_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "catalog_version": self.catalog.catalog_version,
                "state": INSTALLED,
            },
        )

    def _rollback(self, engine_id: str) -> None:
        root = self.paths.engine_dir(engine_id)
        new = root / "venv.new"
        if new.exists():
            shutil.rmtree(new, ignore_errors=True)
        models = self.paths.models(engine_id)
        if models.exists():
            for part in models.rglob("*.part"):
                part.unlink(missing_ok=True)

    def _meta_path(self, engine_id: str) -> Path:
        return self.paths.engine_dir(engine_id) / "engine.json"

    def _read_meta(self, engine_id: str) -> dict[str, object] | None:
        path = self._meta_path(engine_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return None

    def _write_meta(self, engine_id: str, meta: dict[str, object]) -> None:
        path = self._meta_path(engine_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
