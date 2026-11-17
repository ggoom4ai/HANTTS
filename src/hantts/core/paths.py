"""경로 규칙 (docs/02_ARCHITECTURE.md §5)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "HanTTS"


def app_dir() -> Path:
    """설치 폴더 (PyInstaller 번들이면 exe 위치)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def default_data_dir() -> Path:
    portable = app_dir() / "data"
    if (app_dir() / "portable.flag").exists():
        return portable
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


@dataclass(slots=True, frozen=True)
class DataPaths:
    root: Path
    engines_root: Path | None = None

    @property
    def storage(self) -> Path:
        """엔진 가상환경, 모델, 음성, uv 캐시가 놓이는 폴더."""
        return self.engines_root if self.engines_root is not None else self.root

    @property
    def config(self) -> Path:
        return self.root / "config.toml"

    @property
    def db(self) -> Path:
        return self.root / "hantts.db"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def python(self) -> Path:
        return self.storage / "python"

    @property
    def uv_cache(self) -> Path:
        return self.storage / "uv-cache"

    @property
    def tmp(self) -> Path:
        return self.root / "tmp"

    @property
    def output(self) -> Path:
        return self.root / "output"

    def engine_dir(self, engine_id: str) -> Path:
        return self.storage / "engines" / engine_id

    def venv_python(self, engine_id: str) -> Path:
        return self.engine_dir(engine_id) / "venv" / "Scripts" / "python.exe"

    def models(self, engine_id: str) -> Path:
        return self.storage / "models" / engine_id

    def voices(self, engine_id: str) -> Path:
        return self.storage / "voices" / engine_id

    def worker_env(self, engine_id: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        """워커 프로세스 환경변수: 모든 캐시를 엔진 models 폴더로 가둔다."""
        m = self.models(engine_id)
        env = dict(os.environ)
        env.update(
            {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "HF_HOME": str(m / "hf"),
                "HF_HUB_CACHE": str(m / "hf" / "hub"),
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "TORCH_HOME": str(m / "torch"),
                "XDG_CACHE_HOME": str(m / "cache"),
                "NLTK_DATA": str(m / "nltk"),
            }
        )
        env.update(extra or {})
        return env

    def ensure(self) -> None:
        for p in (self.root, self.logs, self.tmp, self.output, self.storage, self.python, self.uv_cache):
            p.mkdir(parents=True, exist_ok=True)
