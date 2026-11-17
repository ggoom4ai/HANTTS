"""config.toml 읽기/쓰기 (docs/02_ARCHITECTURE.md §5, docs/05_UI_SPEC.md §9)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import tomli_w

from hantts.core.paths import DataPaths, default_data_dir


def _default_threads() -> int:
    """합성 중에도 다른 작업이 돌 수 있도록 기본은 4를 넘기지 않는다."""
    return min(4, max(1, (os.cpu_count() or 2) - 1))


@dataclass(slots=True)
class AppConfig:
    language: str = "ko"
    theme: str = "dark"
    font_scale: float = 1.0
    preload_last_engine: bool = False
    threads: int = 0
    max_workers: int = 2
    idle_minutes: int = 2
    data_dir: str = ""
    engines_dir: str = ""
    output_dir: str = ""
    proxy: str = ""
    hf_mirror: str = ""
    check_updates: bool = True
    audio_device: str = ""
    default_format: str = "mp3"
    sample_rate: int = 44100
    lufs: float = -16.0
    log_level: str = "INFO"
    last_engine: str = "windows"
    last_voice: str = ""
    last_lang: str = "ko"
    normalize: bool = True
    expand_acronyms: bool = False
    commercial_use: bool = False
    wizard_done: bool = False
    chunk_silence_ms: int = 300

    def __post_init__(self) -> None:
        if self.threads <= 0:
            self.threads = _default_threads()

    def resolved_data_dir(self) -> Path:
        return Path(self.data_dir) if self.data_dir else default_data_dir()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tomli_w.dumps(self.to_dict()), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> AppConfig:
        if not path.exists():
            cfg = AppConfig()
            return cfg
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(AppConfig)}
        data = {k: v for k, v in raw.items() if k in known}
        return AppConfig(**data)


def open_paths(cfg: AppConfig) -> DataPaths:
    engines = Path(cfg.engines_dir) if cfg.engines_dir else None
    paths = DataPaths(cfg.resolved_data_dir(), engines)
    paths.ensure()
    if cfg.output_dir:
        Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
    return paths
