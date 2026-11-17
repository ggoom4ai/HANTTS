"""오프라인 엔진 팩(.htpack)을 만든다."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--wheels", type=Path, required=True, help="휠이 들어 있는 폴더")
    parser.add_argument("--assets", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    catalog = json.loads(Path("engines/catalog/catalog.json").read_text(encoding="utf-8"))
    entry = next(e for e in catalog["engines"] if e["id"] == args.engine)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "pack.json",
            json.dumps(
                {"engine_id": entry["id"], "version": entry["version"], "catalog": entry},
                ensure_ascii=False,
            ),
        )
        for wheel in args.wheels.glob("*.whl"):
            zf.write(wheel, f"wheels/{wheel.name}")
        if args.assets is not None:
            for file in args.assets.rglob("*"):
                if file.is_file():
                    zf.write(file, f"assets/{file.relative_to(args.assets).as_posix()}")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
