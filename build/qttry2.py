import os, sys, importlib.util
from pathlib import Path
root = Path(r"D:\Project\HANTTS\dist\HanTTS\_internal")
extra = Path(sys.argv[1])
os.add_dll_directory(str(extra))
os.add_dll_directory(str(root / "PySide6"))
os.add_dll_directory(str(root / "shiboken6"))
spec = importlib.util.spec_from_file_location("QtCore", root / "PySide6" / "QtCore.pyd")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("ok", extra)
