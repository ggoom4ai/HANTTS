"""호스트 도메인 예외 (docs/02_ARCHITECTURE.md)."""

from __future__ import annotations


class HanttsError(Exception):
    """사용자가 볼 수 있는 호스트 오류의 기반."""


class CatalogError(HanttsError):
    pass


class DownloadError(HanttsError):
    pass


class InstallError(HanttsError):
    pass


class CancelledError(HanttsError):
    pass


class AudioError(HanttsError):
    pass
