import os, sys, importlib.util
from pathlib import Path
root = Path(r"D:\Project\HANTTS\dist\HanTTS\_internal")
which = sys.argv[1].split(",")
for name in which:
    os.add_dll_directory(str(root / name) if name != "." else str(root))
spec = importlib.util.spec_from_file_location("QtCore", root / "PySide6" / "QtCore.pyd")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("ok", which)
