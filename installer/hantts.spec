# ruff: noqa: F821
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir. torch/onnxruntime/엔진 패키지가 들어가면 빌드를 실패시킨다."""

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

_root = Path(SPECPATH).resolve().parent
_version_src = (_root / "src" / "hantts" / "__init__.py").read_text(encoding="utf-8")
_match = re.search(r'__version__\s*=\s*"([^"]+)"', _version_src)
_version = _match.group(1) if _match else "0.1.0"
_parts = [int(part) if part.isdigit() else 0 for part in _version.split(".")]
while len(_parts) < 4:
    _parts.append(0)
_ver = tuple(_parts[:4])
_version_file = _root / "build" / "version_info.txt"
_version_file.parent.mkdir(parents=True, exist_ok=True)
_version_file.write_text(
    "\n".join(
        [
            "VSVersionInfo(",
            "  ffi=FixedFileInfo(",
            f"    filevers={_ver},",
            f"    prodvers={_ver},",
            "    mask=0x3f,",
            "    flags=0x0,",
            "    OS=0x40004,",
            "    fileType=0x1,",
            "    subtype=0x0,",
            "    date=(0, 0)",
            "  ),",
            "  kids=[",
            "    StringFileInfo([StringTable(",
            "      '040904B0',",
            "      [",
            "        StringStruct('CompanyName', 'HanTTS'),",
            "        StringStruct('FileDescription', 'HanTTS Studio'),",
            f"        StringStruct('FileVersion', '{_version}'),",
            "        StringStruct('InternalName', 'HanTTS'),",
            "        StringStruct('OriginalFilename', 'HanTTS.exe'),",
            "        StringStruct('ProductName', 'HanTTS Studio'),",
            f"        StringStruct('ProductVersion', '{_version}')",
            "      ]",
            "    )]),",
            "    VarFileInfo([VarStruct('Translation', [1033, 1200])])",
            "  ]",
            ")",
            "",
        ]
    ),
    encoding="utf-8",
)

hidden = [
    "winrt.windows.media.speechsynthesis",
    "winrt.windows.storage.streams",
    "winrt.windows.foundation",
    "comtypes.client",
    "PySide6.QtSvg",
    "hantts.engines.windows",
    "hantts.engines.supertonic",
    "hantts.engines.melo",
    "hantts.engines.melo_onnx",
    "hantts.engines.melo_frontend",
    "hantts.engines.melo_frontend.korean",
    "hantts.engines.melo_frontend.wordpiece",
]
hidden += collect_submodules("winrt")

excludes = [
    "torch",
    "onnxruntime",
    "supertonic",
    "melo",
    "transformers",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtMultimedia",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtPdf",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "comtypes.gen",
]

a = Analysis(
    ["../src/hantts/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=[
        ("../src/hantts/app/resources", "hantts/app/resources"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

def _entry_name(entry: object) -> str:
    if isinstance(entry, tuple):
        return str(entry[0])
    return str(entry)


_prefix_root = Path(sys.base_prefix).resolve()
_prefix_bin = _prefix_root / "Library" / "bin"


def _entry_source(entry: object) -> Path | None:
    if isinstance(entry, tuple) and len(entry) >= 2:
        return Path(str(entry[1]))
    return None


def _other_conda_library(src: Path) -> bool:
    """이 인터프리터가 아닌 conda의 Library\\bin 에서 온 DLL."""
    try:
        resolved = src.resolve()
    except OSError:
        return False
    if resolved == _prefix_root or _prefix_root in resolved.parents:
        return False
    parent = resolved.parent
    return parent.name.lower() == "bin" and parent.parent.name.lower() == "library"


def _prepare_binary(entry: object) -> object | None:
    """Anaconda base DLL을 빌드에 쓴 Python의 Library\\bin 것으로 바꾼다.

    base의 libssl/libcrypto 는 _ssl.pyd 가 기대한 심볼이 없고, icuuc.dll 은 Qt6Core와 충돌한다.
    """
    name = _entry_name(entry).replace("\\", "/").rsplit("/", 1)[-1]
    lower = name.lower()
    if lower.startswith("api-ms-win-"):
        return None
    if lower.startswith("icu") and lower.endswith(".dll"):
        return None
    src = _entry_source(entry)
    if src is not None and _other_conda_library(src):
        replacement = _prefix_bin / name
        if not replacement.is_file() or not isinstance(entry, tuple):
            return None
        return (entry[0], str(replacement), *entry[2:])
    return entry


a.binaries = [kept for entry in a.binaries if (kept := _prepare_binary(entry)) is not None]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HanTTS",
    console=False,
    icon="hantts.ico",
    version=str(_version_file),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="HanTTS",
)

# 우리 어댑터 모듈 이름(hantts.engines.melo)은 통과시키고, 최상위 엔진 패키지만 막는다.
_roots = {_entry_name(entry).split(".", 1)[0].lower() for entry in a.pure}
_forbidden = {"torch", "onnxruntime", "supertonic", "melo", "transformers"}
leaked = sorted(_roots & _forbidden)
for entry in a.binaries:
    bin_name = _entry_name(entry).replace("\\", "/").lower()
    if "onnxruntime" in bin_name or bin_name.endswith("/torch.dll") or "/torch/" in bin_name:
        leaked.append(bin_name)
if leaked:
    raise SystemExit("호스트 번들에 엔진 런타임이 포함되었습니다: " + ", ".join(leaked[:20]))
