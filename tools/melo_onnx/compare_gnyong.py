"""gnyong/melotts-kr-onnx 검증·비교 스크립트 (docs/14_MELO_ONNX.md §2).

같은 문장을 세 방식으로 합성해 wav 와 요약표를 만든다.
  (a) torch  : 원본 PyTorch MeloTTS (기준)
  (b) onnx_bert : gnyong ONNX + 실제 한국어 BERT 특징(ja_bert)
  (c) onnx_zero : gnyong ONNX + BERT 0 (모델 카드 방식)
추가로 노이즈 0 조건에서 (a)와 (b)의 파형 차이를 재 export 가 원본과 같은지 확인한다.

변환 환경(14 문서 3절의 build\\melo-export)에서 실행:
    python tools\\melo_onnx\\compare_gnyong.py --revision <커밋> --model fp32 --out build\\melo_compare
    python tools\\melo_onnx\\compare_gnyong.py ... --model int8      # int8 음질 비교
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
import torch

REPO = "gnyong/melotts-kr-onnx"
FILES = {
    "fp32": "melotts_kr_fp32.onnx",
    "fp16": "melotts_kr_fp16.onnx",
    "int8": "melotts_kr_int8.onnx",
    "fp16_no_bert": "melotts_kr_fp16_no_bert.onnx",
}
# manifest.json (커밋 a21b7e0 기준) 의 SHA256 — fp16_no_bert 는 manifest 에 없음
SHA256 = {
    "melotts_kr_fp32.onnx": "a2450570c59a18361717842c25a1800cb8a67d150d9b3f1dc05d253c4e2220e9",
    "melotts_kr_fp16.onnx": "0d186c0b35e5376d1ab787dc3ceea9d5c6019aa1603c39cae32c7094cc6288b5",
    "melotts_kr_int8.onnx": "421b94ce7e803fdd0126c7d39d90192b64878794619668cf3ec12611fc860f88",
    "symbols.json": "bf8d22eefcbe576116e4c5b6e1dcef1b3d59fa1ed5333007048a901a84aa1bc3",
    "melotts_kr_config.json": "74543376976dfadde45ba34336fa79c7e95509f43a7c2e701b22c0f71fd7695c",
}
SENTENCES = [
    "안녕하세요. 반갑습니다.",
    "오늘은 2026년 11월 16일, 새 프로젝트를 시작하는 날입니다.",
    "정말요? 그럼 내일 오후 세 시에 다시 만나서 이야기해요!",
    "긴 원고는 문장 단위로 나누어 만들고, 마지막에 하나로 합쳐서 하나의 파일로 저장합니다.",
]
DEFAULTS = {"noise_scale": 0.6, "length_scale": 1.0, "noise_scale_w": 0.8, "sdp_ratio": 0.2}
ZERO_NOISE = {"noise_scale": 0.0, "length_scale": 1.0, "noise_scale_w": 0.0, "sdp_ratio": 0.0}


def sha256(p: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(name: str, revision: str, cache: Path) -> Path:
    from huggingface_hub import hf_hub_download

    p = Path(hf_hub_download(REPO, name, revision=revision, cache_dir=str(cache)))
    want = SHA256.get(name)
    if want and sha256(p) != want:
        raise SystemExit(f"SHA256 불일치: {name} (저장소가 바뀌었을 수 있음)")
    return p


class GnyongOnnx:
    """입력 이름·차원을 세션에서 읽어 맞춘다 (tone/tones, language/lang_ids, 스칼라 0차원/1차원 모두 대응)."""

    ALIASES = {"tone": "tones", "tones": "tones", "language": "lang_ids", "lang_ids": "lang_ids"}

    def __init__(self, path: Path, threads: int) -> None:
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
        self.inputs = {i.name: i for i in self.sess.get_inputs()}
        self.out = self.sess.get_outputs()[0].name
        print("  ONNX 입력:", [(i.name, i.type, i.shape) for i in self.sess.get_inputs()])

    def run(self, t: dict[str, np.ndarray], params: dict[str, float]) -> np.ndarray:
        feeds: dict[str, np.ndarray] = {}
        for name, meta in self.inputs.items():
            key = self.ALIASES.get(name, name)
            if key in params:
                dt = np.float16 if "float16" in meta.type else np.float32
                v = params[key]
                feeds[name] = np.array(v, dtype=dt) if len(meta.shape) == 0 else np.array([v], dtype=dt)
            else:
                arr = t[key]
                feeds[name] = arr.astype(np.float16 if "float16" in meta.type else arr.dtype)
        return np.asarray(self.sess.run([self.out], feeds)[0], dtype=np.float32).reshape(-1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", required=True, help="gnyong/melotts-kr-onnx 전체 커밋 해시 (main 금지)")
    ap.add_argument("--model", choices=list(FILES), default="fp32")
    ap.add_argument("--out", default="build/melo_compare")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out) / a.model
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(a.out) / "hf"

    print("[1/4] 파일 받기 + SHA256 확인")
    onnx_path = fetch(FILES[a.model], a.revision, cache)
    symbols_path = fetch("symbols.json", a.revision, cache)
    cfg = json.loads(fetch("melotts_kr_config.json", a.revision, cache).read_text(encoding="utf-8"))
    sr = int(cfg["data"]["sampling_rate"])

    print("[2/4] 원본 MeloTTS 로드 + 심볼 표 일치 확인")
    from melo.api import TTS
    from melo.text.symbols import symbols as melo_symbols
    from melo.utils import get_text_for_tts_infer

    tts = TTS(language="KR", device="cpu")
    g_sym = json.loads(symbols_path.read_text(encoding="utf-8"))
    g_list = g_sym.get("symbols") if isinstance(g_sym, dict) else g_sym
    if isinstance(g_list, list) and list(g_list) != list(melo_symbols):
        raise SystemExit("심볼 표가 원본 MeloTTS 와 다릅니다. symbols.json 기준으로 맞추세요.")
    print("  심볼 표:", "일치" if isinstance(g_list, list) else f"형식 확인 필요 ({type(g_sym).__name__})")

    print("[3/4] ONNX 세션")
    onnx = GnyongOnnx(onnx_path, a.threads)
    torch.set_num_threads(a.threads)

    print("[4/4] 합성·비교")
    rows = []
    for i, text in enumerate(SENTENCES):
        bert, ja_bert, phones, tones, lang_ids = get_text_for_tts_infer(
            text, "KR", tts.hps, "cpu", tts.symbol_to_id
        )
        x = phones.unsqueeze(0)
        t = {
            "x": x.numpy().astype(np.int64),
            "x_lengths": np.array([x.shape[1]], np.int64),
            "sid": np.array([0], np.int64),
            "tones": tones.unsqueeze(0).numpy().astype(np.int64),
            "lang_ids": lang_ids.unsqueeze(0).numpy().astype(np.int64),
            "bert": bert.unsqueeze(0).numpy().astype(np.float32),
            "ja_bert": ja_bert.unsqueeze(0).numpy().astype(np.float32),
        }
        t_zero = {**t, "bert": np.zeros_like(t["bert"]), "ja_bert": np.zeros_like(t["ja_bert"])}

        def torch_run(
            p: dict[str, float],
            phones_x: torch.Tensor = x,
            tone_t: torch.Tensor = tones,
            lang_t: torch.Tensor = lang_ids,
            bert_t: torch.Tensor = bert,
            ja_t: torch.Tensor = ja_bert,
        ) -> np.ndarray:
            with torch.no_grad():
                audio = tts.model.infer(
                    phones_x,
                    torch.LongTensor([phones_x.shape[1]]),
                    torch.LongTensor([0]),
                    tone_t.unsqueeze(0),
                    lang_t.unsqueeze(0),
                    bert_t.unsqueeze(0),
                    ja_t.unsqueeze(0),
                    **p,
                )
                return audio[0][0, 0].numpy()

        # 결정적 비교 (변환 정확도)
        ref0, got0 = torch_run(ZERO_NOISE), onnx.run(t, ZERO_NOISE)
        n = min(len(ref0), len(got0))
        diff = float(np.max(np.abs(ref0[:n] - got0[:n]))) if n else float("nan")

        # 청취용 3종
        res = {}
        runs = (
            ("a_torch", lambda params=DEFAULTS: torch_run(params)),
            ("b_onnx_bert", lambda feeds=t: onnx.run(feeds, DEFAULTS)),
            ("c_onnx_zero", lambda feeds=t_zero: onnx.run(feeds, DEFAULTS)),
        )
        for tag, fn in runs:
            s = time.perf_counter()
            audio = fn()
            el = time.perf_counter() - s
            sf.write(out / f"{i:02d}_{tag}.wav", audio, sr)
            res[tag] = (len(audio) / sr, el)
        row = {
            "idx": i,
            "text": text,
            "len_torch0": len(ref0),
            "len_onnx0": len(got0),
            "maxdiff0": f"{diff:.2e}",
        }
        row.update({f"{k}_sec": f"{v[0]:.2f}" for k, v in res.items()})
        row.update({f"{k}_rtf": f"{v[1] / max(v[0], 1e-6):.3f}" for k, v in res.items()})
        rows.append(row)
        print(
            f"  [{i}] 노이즈0 길이 {len(ref0)}/{len(got0)} 최대차이 {diff:.2e} | "
            + " ".join(f"{k} RTF {v[1] / max(v[0], 1e-6):.3f}" for k, v in res.items())
        )

    with (out / "summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("결과:", out.resolve())
    print("a/b/c wav 를 들어보고 docs/spike_report.md 에 판정을 기록하세요.")


if __name__ == "__main__":
    main()
