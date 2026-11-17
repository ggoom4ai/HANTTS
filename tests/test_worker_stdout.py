from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_protocol_stdout_stays_open_after_library_writes() -> None:
    src = Path(__file__).resolve().parents[1] / "src"
    code = (
        "from hantts.worker.main import _isolate_stdout\n"
        "import os\n"
        "proto = _isolate_stdout()\n"
        "proto.write('OK\\n')\n"
        "proto.flush()\n"
        "os.write(1, b'LOG\\n')\n"
    )
    env = dict(os.environ, PYTHONPATH=str(src), PYTHONUTF8="1")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout == b"OK\n"
    assert b"LOG\n" in proc.stderr
