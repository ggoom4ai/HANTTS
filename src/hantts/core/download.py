"""스트리밍 다운로더: 이어받기, SHA256, 미러, 재시도 (docs/04_ENGINE_MANAGER.md §4)."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import truststore

from hantts.core.catalog import Asset
from hantts.core.errors import CancelledError, DownloadError

truststore.inject_into_ssl()

ProgressCb = Callable[[int, int, float, float | None], None]
CHUNK = 1024 * 1024


@dataclass(slots=True)
class CancelToken:
    _flag: threading.Event

    def __init__(self) -> None:
        self._flag = threading.Event()

    def cancel(self) -> None:
        self._flag.set()

    def raise_if_cancelled(self) -> None:
        if self._flag.is_set():
            raise CancelledError("다운로드가 취소되었습니다.")


def _rewrite(url: str, hf_mirror: str) -> str:
    if hf_mirror and "huggingface.co" in url:
        return url.replace("https://huggingface.co", hf_mirror.rstrip("/")).replace(
            "http://huggingface.co", hf_mirror.rstrip("/")
        )
    return url


def download_asset(
    asset: Asset,
    dest: Path,
    *,
    proxy: str = "",
    hf_mirror: str = "",
    cancel: CancelToken | None = None,
    on_progress: ProgressCb | None = None,
    retries: int = 3,
    client: httpx.Client | None = None,
) -> Path:
    """자산을 dest 에 저장한다. SHA256 이 유효하지 않으면 거부한다."""
    if not asset.verified:
        raise DownloadError(f"SHA256 이 확정되지 않은 자산은 받을 수 없습니다: {asset.dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    if dest.exists() and _sha256(dest) == asset.sha256:
        if on_progress:
            size = dest.stat().st_size
            on_progress(size, size, 0.0, 0.0)
        return dest

    own = client is None
    http = client or httpx.Client(
        proxy=proxy or None, follow_redirects=True, timeout=httpx.Timeout(30.0, read=120.0)
    )
    try:
        last_err: Exception | None = None
        for url in asset.urls:
            url = _rewrite(url, hf_mirror)
            for attempt in range(retries):
                if cancel:
                    cancel.raise_if_cancelled()
                try:
                    _fetch(http, url, part, asset, cancel, on_progress)
                    digest = _sha256(part)
                    if digest != asset.sha256:
                        part.unlink(missing_ok=True)
                        raise DownloadError(f"SHA256 불일치: {asset.dest}")
                    part.replace(dest)
                    return dest
                except CancelledError:
                    raise
                except (DownloadError, httpx.HTTPError, OSError) as e:
                    last_err = e
                    time.sleep(min(8.0, 0.4 * (2**attempt)))
        raise DownloadError(f"모든 미러에서 받지 못했습니다: {asset.dest} ({last_err})")
    finally:
        if own:
            http.close()


def _fetch(
    http: httpx.Client,
    url: str,
    part: Path,
    asset: Asset,
    cancel: CancelToken | None,
    on_progress: ProgressCb | None,
) -> None:
    offset = part.stat().st_size if part.exists() else 0
    headers: dict[str, str] = {}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    started = time.perf_counter()
    base = offset
    with http.stream("GET", url, headers=headers) as resp:
        if resp.status_code == 416:
            part.unlink(missing_ok=True)
            raise DownloadError("이어받기 범위가 거부되었습니다.")
        if offset and resp.status_code != 206:
            offset = 0
            base = 0
            part.write_bytes(b"")
        resp.raise_for_status()
        total = _total(resp, offset, asset.size)
        with part.open("ab" if offset else "wb") as fh:
            for chunk in resp.iter_bytes(CHUNK):
                if cancel:
                    cancel.raise_if_cancelled()
                if not chunk:
                    continue
                fh.write(chunk)
                base += len(chunk)
                if on_progress:
                    elapsed = max(time.perf_counter() - started, 1e-6)
                    speed = (base - offset) / elapsed
                    remain = (total - base) / speed if total and speed else None
                    on_progress(base, total, speed, remain)


def _total(resp: httpx.Response, offset: int, fallback: int) -> int:
    content_range = resp.headers.get("content-range")
    if content_range and "/" in content_range:
        tail = content_range.rsplit("/", 1)[-1]
        if tail.isdigit():
            return int(tail)
    length = resp.headers.get("content-length")
    if length and length.isdigit():
        return offset + int(length)
    return fallback


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()
