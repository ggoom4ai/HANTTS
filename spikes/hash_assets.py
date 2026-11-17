"""로컬에 있는 모델 파일의 SHA256을 카탈로그와 대조한다.

파일이 없으면 건너뛰고, 카탈로그를 다시 쓰지 않는다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from hantts.core.catalog import load_catalog


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    catalog = load_catalog(root / "engines" / "catalog" / "catalog.json")
    models = root / "models"
    bad = 0
    seen = 0
    for engine in catalog.engines:
        for asset in engine.assets:
            path = models / engine.id / asset.dest
            if not path.is_file():
                continue
            seen += 1
            got = _sha(path)
            if got != asset.sha256:
                bad += 1
                print(f"mismatch {engine.id}/{asset.dest}")
    print(f"checked {seen} local files, mismatches {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
