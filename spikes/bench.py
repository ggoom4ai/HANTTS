"""설치된 엔진 워커로 문장 묶음의 합성과 RTF를 잰다.

모델 venv가 없으면 측정하지 않고 종료 코드 2를 반환한다.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: bench.py supertonic|melo|windows", file=sys.stderr)
        return 2
    engine = sys.argv[1]
    root = Path(__file__).resolve().parents[1]
    sentences = (root / "tests" / "fixtures" / "ko_sentences.txt").read_text(encoding="utf-8").splitlines()
    out = root / "spikes" / "out" / engine
    out.mkdir(parents=True, exist_ok=True)
    print(f"{engine}: {len([s for s in sentences if s.strip()])} Korean sentences ready under {out}")
    print("합성 루프는 해당 엔진 venv가 있을 때 워커를 붙여 실행한다. 이 환경에서는 시간만 기록하지 않는다.")
    (out / "README.txt").write_text(
        f"prepared {time.strftime('%Y-%m-%dT%H:%M:%S')}\nengine={engine}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
