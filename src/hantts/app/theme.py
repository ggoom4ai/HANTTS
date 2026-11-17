"""테마 로더: tokens.json → QSS 템플릿 치환 → QApplication 적용 (docs/12_UI_DESIGN.md §6)."""

from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QWidget

RES = Path(__file__).resolve().parent / "resources"
_PLACEHOLDER = re.compile(r"\$\{([a-z0-9_.]+)\}")


@lru_cache(maxsize=1)
def tokens() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((RES / "tokens.json").read_text(encoding="utf-8"))
    return data


def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        elif not isinstance(v, list):
            out[key] = str(v)
    return out


def color(name: str) -> QColor:
    """커스텀 위젯(paintEvent)용 색상 조회. 예: color("accent")"""
    return QColor(tokens()["color"][name])


def render_qss(theme: str = "dark") -> str:
    flat = _flatten(tokens())
    src = (RES / "themes" / f"{theme}.qss").read_text(encoding="utf-8")

    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in flat:
            raise KeyError(f"QSS placeholder not in tokens.json: {key}")
        return flat[key]

    return _PLACEHOLDER.sub(sub, src)


def load_fonts() -> None:
    """resources/fonts/*.ttf|otf 를 등록 (IBM Plex Sans KR, JetBrains Mono — 둘 다 OFL)."""
    for f in sorted((RES / "fonts").glob("*.[to]tf")):
        QFontDatabase.addApplicationFont(str(f))


def apply(app: QApplication, theme: str = "dark") -> None:
    load_fonts()
    t = tokens()
    font = QFont(t["font"]["family_ui"])
    if font.family() != t["font"]["family_ui"]:
        font = QFont(t["font"]["fallback_ui"])
    font.setPixelSize(int(t["font"]["size"]["base"]))
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)

    c = t["color"]
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(c["bg"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(c["surface"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(c["surface_alt"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(c["surface"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(c["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(c["on_accent"]))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["text_faint"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["surface_raised"]))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text"]))
    app.setPalette(pal)
    app.setStyle("Fusion")  # 플랫폼 스타일 차이를 없애고 QSS를 일관되게 적용
    app.setStyleSheet(render_qss(theme))


def dark_title_bar(widget: QWidget) -> None:
    """Windows 10 20H1+/11: 네이티브 타이틀바를 다크로 (DWMWA_USE_IMMERSIVE_DARK_MODE=20)."""
    if sys.platform != "win32":
        return
    import ctypes

    hwnd = int(widget.winId())
    value = ctypes.c_int(1)
    for attr in (20, 19):  # 19 = 구버전 빌드
        if (
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
            == 0
        ):
            break


def set_prop(widget: QWidget, **props: object) -> None:
    """동적 속성 변경 + 스타일 재적용. 예: set_prop(card, selected=True)"""
    for k, v in props.items():
        widget.setProperty(k, "true" if v is True else "false" if v is False else v)
    st = widget.style()
    st.unpolish(widget)
    st.polish(widget)
    widget.update()
