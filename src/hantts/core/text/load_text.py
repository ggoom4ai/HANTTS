"""txt, md, srt, docx 를 원고 문자열로 읽는다."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def read_text_file(path: str | Path) -> str:
    file = Path(path)
    suffix = file.suffix.lower()
    if suffix == ".docx":
        return _docx(file)
    raw = file.read_text(encoding="utf-8")
    if suffix == ".srt":
        return _srt(raw)
    return raw


def _srt(raw: str) -> str:
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.isdigit() or "-->" in stripped:
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _docx(path: Path) -> str:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    for para in root.iter(f"{ns}p"):
        texts = [node.text or "" for node in para.iter(f"{ns}t")]
        paragraphs.append("".join(texts))
    return "\n".join(paragraphs)
