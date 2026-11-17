"""PyTorch MeloTTS 와 ONNX 변환본의 출력을 비교한다 (export 와 같은 변환 환경에서 실행).

무작위성을 없애기 위해 noise_scale=0, noise_scale_w=0 으로 두 경로를 돌려 파형을 비교하고,
기본 파라미터로 만든 wav 를 사람이 들어볼 수 있게 저장한다.

    python tools\\melo_onnx\\verify_melo_onnx.py --dir build\\melo_onnx --lang KR
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
import torch

SENTENCES = [
    "안녕하세요. 반갑습니다.",
    "오늘은 2026년 11월 16일, 새 프로젝트를 시작하는 날입니다.",
    "긴 원고는 문장 단위로 나누어 만들고, 마지막에 하나로 합칩니다.",
]


def bert_onnx_features(sess: ort.InferenceSession, tok, text: str, word2ph: list[int]) -> np.ndarray:
    """melo japanese_bert.get_bert_feature 의 ONNX 판: [768, n_phones]."""
    enc = tok(text, return_tensors="np")
    hidden = sess.run(
        ["hidden"], {k: enc[k].astype(np.int64) for k in ("input_ids", "attention_mask", "token_type_ids")}
    )[0][0]
    assert hidden.shape[0] == len(word2ph), (hidden.shape, len(word2ph))
    return np.repeat(hidden, word2ph, axis=0).T.astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="build/melo_onnx")
    ap.add_argument("--lang", default="KR")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    d = Path(a.dir)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))

    from melo.api import TTS
    from melo.utils import get_text_for_tts_infer
    from transformers import AutoTokenizer

    tts = TTS(language=a.lang, device="cpu")
    so = ort.SessionOptions()
    so.intra_op_num_threads = a.threads
    model_path = d / f"melo_{a.lang.lower()}.onnx"
    vits = ort.InferenceSession(str(model_path), so, providers=["CPUExecutionProvider"])
    bert_path = d / f"bert_{a.lang.lower()}.int8.onnx"
    if not bert_path.exists():
        bert_path = d / f"bert_{a.lang.lower()}.onnx"
    bert_sess = ort.InferenceSession(str(bert_path), so, providers=["CPUExecutionProvider"])
    AutoTokenizer.from_pretrained(d / "tokenizer")
    sr = meta["sampling_rate"]
    (d / "verify").mkdir(exist_ok=True)

    for i, text in enumerate(SENTENCES):
        bert, ja_bert, phones, tones, lang_ids = get_text_for_tts_infer(
            text, a.lang, tts.hps, "cpu", tts.symbol_to_id
        )
        x = phones.unsqueeze(0)
        feeds_base = {
            "x": x.numpy().astype(np.int64),
            "x_lengths": np.array([x.shape[1]], dtype=np.int64),
            "sid": np.array([0], dtype=np.int64),
            "tones": tones.unsqueeze(0).numpy().astype(np.int64),
            "lang_ids": lang_ids.unsqueeze(0).numpy().astype(np.int64),
            "bert": bert.unsqueeze(0).numpy().astype(np.float32),
            "ja_bert": ja_bert.unsqueeze(0).numpy().astype(np.float32),
        }

        # (1) 결정적 비교: 같은 BERT 특징, 노이즈 0
        det = {"noise_scale": [0.0], "length_scale": [1.0], "noise_scale_w": [0.0], "sdp_ratio": [0.0]}
        with torch.no_grad():
            raw = tts.model.infer(
                x,
                torch.LongTensor([x.shape[1]]),
                torch.LongTensor([0]),
                tones.unsqueeze(0),
                lang_ids.unsqueeze(0),
                bert.unsqueeze(0),
                ja_bert.unsqueeze(0),
                noise_scale=0.0,
                length_scale=1.0,
                noise_scale_w=0.0,
                sdp_ratio=0.0,
            )
            ref = raw[0][0, 0].numpy()
        det_feeds = {key: np.array(val, np.float32) for key, val in det.items()}
        got = vits.run(["audio"], {**feeds_base, **det_feeds})[0][0, 0]
        n = min(len(ref), len(got))
        diff = float(np.max(np.abs(ref[:n] - got[:n]))) if n else float("nan")
        print(f"[{i}] 길이 torch={len(ref)} onnx={len(got)}  최대 차이={diff:.2e}")

        # (2) BERT 도 ONNX 로 바꾼 전체 ONNX 경로 + 기본 파라미터 → 청취용 wav
        # word2ph 는 melo 내부 값이 필요하므로 여기서는 torch BERT 특징 길이로 대체 검증만 한다.
        t = time.perf_counter()
        audio = vits.run(
            ["audio"],
            {
                **feeds_base,
                "noise_scale": np.array([0.6], np.float32),
                "length_scale": np.array([1.0], np.float32),
                "noise_scale_w": np.array([0.8], np.float32),
                "sdp_ratio": np.array([0.2], np.float32),
            },
        )[0][0, 0]
        el = time.perf_counter() - t
        sf.write(d / "verify" / f"onnx_{i}.wav", audio, sr)
        print(f"    합성 {el:.2f}s / 음성 {len(audio) / sr:.2f}s  (RTF {el / (len(audio) / sr):.3f})")

    _ = bert_sess  # 앱 쪽 프런트엔드 이식 후 bert_onnx_features() 로 전체 경로 검증 (docs/14 4단계)
    print("청취용 파일:", (d / "verify").resolve())


if __name__ == "__main__":
    main()
