"""아이콘: SVG 의 currentColor 를 토큰 색으로 바꿔 QIcon 으로 캐시한다."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from hantts.app.theme import RES, color

_ICON = 22


@lru_cache(maxsize=128)
def _pixmap(name: str, token: str, px: int, dpr_key: int) -> QPixmap:
    raw = (RES / "icons" / f"{name}.svg").read_text(encoding="utf-8")
    raw = raw.replace("currentColor", color(token).name())
    renderer = QSvgRenderer(QByteArray(raw.encode("utf-8")))
    dpr = dpr_key / 100
    pm = QPixmap(int(px * dpr), int(px * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def app_icon() -> QIcon:
    """창 아이콘. 작업 표시줄 아이콘은 설치본 exe 에 박힌 hantts.ico 가 담당한다."""
    return QIcon(str(RES / "icons" / "app.svg"))


def icon(name: str, color_token: str = "text", px: int = _ICON) -> QIcon:
    screen = QGuiApplication.primaryScreen()
    dpr = 1.0 if screen is None else float(screen.devicePixelRatio())
    return QIcon(_pixmap(name, color_token, px, int(round(dpr * 100))))
