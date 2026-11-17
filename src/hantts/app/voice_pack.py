"""Windows 한국어 음성 팩 (docs/04_ENGINE_MANAGER.md §8)."""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

SPEECH_SETTINGS = "ms-settings:speech"
CAPABILITY = "Language.TextToSpeech~~~ko-KR~0.0.1.0"


def open_speech_settings() -> None:
    QDesktopServices.openUrl(QUrl(SPEECH_SETTINGS))


def install_korean_voice() -> bool:
    """UAC 승인을 요청하고 바로 반환한다. 성공 여부는 나중에 음성 목록으로 확인한다."""
    if sys.platform != "win32":
        return False
    command = f"Add-WindowsCapability -Online -Name '{CAPABILITY}'"
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "powershell.exe", f"-NoProfile -Command {command}", None, 1
    )
    return int(result) > 32
