"""엔진 카탈로그 로드·검증 (docs/04_ENGINE_MANAGER.md §3)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hantts.core.errors import CatalogError

_SHA = re.compile(r"^[0-9a-f]{64}$")
_HF = re.compile(r"https?://[^/]*huggingface\.co/.+/resolve/([0-9a-f]{7,40})/", re.IGNORECASE)
_HF_MIRROR = re.compile(r"https?://[^/]*hf-mirror\.com/.+/resolve/([0-9a-f]{7,40})/", re.IGNORECASE)
_MAIN = re.compile(r"/resolve/main/", re.IGNORECASE)
_REQUIRED = ("id", "display_name", "version", "runtime")


@dataclass(slots=True, frozen=True)
class Asset:
    dest: str
    sha256: str
    size: int
    urls: tuple[str, ...]

    @property
    def verified(self) -> bool:
        return bool(_SHA.match(self.sha256))


@dataclass(slots=True, frozen=True)
class LicenseInfo:
    name: str
    url: str
    requires_consent: bool
    default_checked: bool = False


@dataclass(slots=True, frozen=True)
class PostStep:
    type: str
    module: str
    args: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class EngineEntry:
    id: str
    display_name: str
    description_ko: str
    version: str
    korean_support: str
    runtime: str
    python: str
    approx_disk_mb: int
    approx_ram_mb: int
    lock_file: str
    extra_index_urls: tuple[str, ...]
    post_install: tuple[PostStep, ...]
    assets: tuple[Asset, ...]
    licenses: tuple[LicenseInfo, ...]
    notices_ko: tuple[str, ...]
    worker_env: dict[str, str]
    requirements: tuple[dict[str, Any], ...]
    worker_command: str
    worker_args: tuple[str, ...]
    raw: dict[str, Any] = field(repr=False, compare=False)


@dataclass(slots=True, frozen=True)
class CatalogWarning:
    engine_id: str
    message: str


@dataclass(slots=True)
class Catalog:
    schema_version: int
    catalog_version: str
    engines: tuple[EngineEntry, ...]
    warnings: tuple[CatalogWarning, ...]
    path: Path

    def get(self, engine_id: str) -> EngineEntry | None:
        return next((e for e in self.engines if e.id == engine_id), None)

    def require(self, engine_id: str) -> EngineEntry:
        entry = self.get(engine_id)
        if entry is None:
            raise CatalogError(f"카탈로그에 엔진이 없습니다: {engine_id}")
        return entry


def load_catalog(path: Path) -> Catalog:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise CatalogError(f"카탈로그를 읽지 못했습니다: {path}") from e
    if not isinstance(data, dict) or "engines" not in data:
        raise CatalogError("catalog.json 에 engines 배열이 필요합니다.")
    warnings: list[CatalogWarning] = []
    engines: list[EngineEntry] = []
    seen: set[str] = set()
    for raw in data["engines"]:
        if not isinstance(raw, dict):
            raise CatalogError("엔진 항목은 객체여야 합니다.")
        for key in _REQUIRED:
            if not raw.get(key):
                raise CatalogError(f"엔진 필수 필드 누락: {key}")
        eid = str(raw["id"])
        if eid in seen:
            raise CatalogError(f"엔진 id 중복: {eid}")
        seen.add(eid)
        assets = tuple(_asset(eid, a, warnings) for a in raw.get("assets") or [])
        _check_urls(eid, assets, warnings)
        worker = raw.get("worker") or {}
        engines.append(
            EngineEntry(
                id=eid,
                display_name=str(raw["display_name"]),
                description_ko=str(raw.get("description_ko") or ""),
                version=str(raw["version"]),
                korean_support=str(raw.get("korean_support") or "none"),
                runtime=str(raw["runtime"]),
                python=str(raw.get("python") or ""),
                approx_disk_mb=int(raw.get("approx_disk_mb") or 0),
                approx_ram_mb=int(raw.get("approx_ram_mb") or 0),
                lock_file=str(raw.get("lock_file") or ""),
                extra_index_urls=tuple(str(u) for u in raw.get("extra_index_urls") or []),
                post_install=tuple(
                    PostStep(
                        str(s.get("type") or "python"),
                        str(s.get("module") or ""),
                        tuple(str(a) for a in s.get("args") or []),
                    )
                    for s in raw.get("post_install") or []
                ),
                assets=assets,
                licenses=tuple(
                    LicenseInfo(
                        str(lic["name"]),
                        str(lic.get("url") or ""),
                        bool(lic.get("requires_consent")),
                        bool(lic.get("default_checked")),
                    )
                    for lic in raw.get("licenses") or []
                ),
                notices_ko=tuple(str(n) for n in raw.get("notices_ko") or []),
                worker_env={str(k): str(v) for k, v in (raw.get("worker_env") or {}).items()},
                requirements=tuple(dict(r) for r in raw.get("requirements") or []),
                worker_command=str(worker.get("command") or ""),
                worker_args=tuple(str(a) for a in worker.get("args") or []),
                raw=raw,
            )
        )
    return Catalog(
        schema_version=int(data.get("schema_version") or 1),
        catalog_version=str(data.get("catalog_version") or ""),
        engines=tuple(engines),
        warnings=tuple(warnings),
        path=path,
    )


def _asset(engine_id: str, raw: dict[str, Any], warnings: list[CatalogWarning]) -> Asset:
    sha = str(raw.get("sha256") or "").lower()
    urls = tuple(str(u) for u in raw.get("urls") or [])
    if not raw.get("dest") or not urls:
        raise CatalogError(f"{engine_id}: 자산 dest/urls 가 필요합니다.")
    if not _SHA.match(sha):
        warnings.append(
            CatalogWarning(engine_id, f"자산 {raw.get('dest')} 의 sha256 이 비어 있거나 형식이 아닙니다.")
        )
    return Asset(dest=str(raw["dest"]), sha256=sha, size=int(raw.get("size") or 0), urls=urls)


def _check_urls(engine_id: str, assets: tuple[Asset, ...], warnings: list[CatalogWarning]) -> None:
    for asset in assets:
        for url in asset.urls:
            if _MAIN.search(url):
                warnings.append(CatalogWarning(engine_id, f"main 브랜치 URL 은 금지입니다: {url}"))
            elif ("huggingface.co" in url or "hf-mirror.com" in url) and not (
                _HF.search(url) or _HF_MIRROR.search(url)
            ):
                warnings.append(CatalogWarning(engine_id, f"커밋이 고정되지 않은 URL: {url}"))
