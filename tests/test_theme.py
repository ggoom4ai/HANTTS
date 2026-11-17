from __future__ import annotations

import re
from pathlib import Path

from hantts.app.theme import render_qss

_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}")


def test_qss_placeholders_resolved() -> None:
    css = render_qss("dark")
    assert "${" not in css
    assert "#7C8CFF" in css or "7C8CFF" in css.upper()


def test_python_has_no_hex_colors() -> None:
    root = Path("src/hantts/app")
    hits: list[str] = []
    for path in root.rglob("*.py"):
        if "resources" in path.parts:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _HEX.search(line) and "noqa" not in line:
                hits.append(f"{path}:{lineno}:{line.strip()}")
    assert hits == []
