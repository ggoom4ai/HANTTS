"""MeloTTS(한국어) → ONNX 변환 스크립트 (docs/14_MELO_ONNX.md).

개발 PC에서 1회 실행한다. 사용자 PC에는 결과물(.onnx + meta.json + tokenizer)만 배포한다.

변환 환경 (사용자 앱과 별개):
    uv venv build\\melo-export --python 3.10
    uv pip install --python build\\melo-export\\Scripts\\python.exe ^
        torch --index-url https://download.pytorch.org/whl/cpu
    uv pip install --python build\\melo-export\\Scripts\\python.exe ^
        "git+https://github.com/myshell-ai/MeloTTS@<커밋>" onnx onnxruntime
    # 일본어 모듈 import 시 unidic 이 필요할 수 있다.
    build\\melo-export\\Scripts\\python.exe -m unidic download

실행:
    python tools\\melo_onnx\\export_melo_onnx.py --out build\\melo_onnx --lang KR --quantize-bert

결과:
    build/melo_onnx/
      melo_kr.onnx          VITS 합성기 (음소·성조·BERT 특징 → 파형)
      bert_kr.onnx          한국어 BERT 특징 추출기 (hidden_states[-3])
      bert_kr.int8.onnx     (--quantize-bert 시) 동적 int8 양자화본
      tokenizer/            BERT 토크나이저 파일
      meta.json             샘플레이트, add_blank, 화자, 심볼 표, 입력 순서, 기본 파라미터
"""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

import torch

BERT_IDS = {"KR": "kykim/bert-kor-base"}  # melo/text/korean.py 기본 model_id 와 일치해야 함 (Phase 0 확인)
SAMPLE_TEXT = {"KR": "안녕하세요. 멜로 TTS를 ONNX로 변환하는 테스트 문장입니다."}


class VitsWrapper(torch.nn.Module):
    """melo.models.SynthesizerTrn.infer 를 ONNX 로 내보내기 위한 래퍼.

    스칼라 파라미터(noise_scale 등)를 텐서 입력으로 받아 런타임에 바꿀 수 있게 한다.
    """

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.m = model

    def forward(
        self,
        x,
        x_lengths,
        sid,
        tones,
        lang_ids,
        bert,
        ja_bert,  # type: ignore[no-untyped-def]
        noise_scale,
        length_scale,
        noise_scale_w,
        sdp_ratio,
    ):
        out = self.m.infer(
            x,
            x_lengths,
            sid,
            tones,
            lang_ids,
            bert,
            ja_bert,
            noise_scale=noise_scale,
            length_scale=length_scale,
            noise_scale_w=noise_scale_w,
            sdp_ratio=sdp_ratio,
        )
        return out[0]  # [1, 1, T_wav]


class BertWrapper(torch.nn.Module):
    """melo 의 get_bert_feature 와 같은 층(hidden_states[-3])을 돌려준다."""

    def __init__(self, bert: torch.nn.Module, layer: int = -3) -> None:
        super().__init__()
        self.bert = bert
        self.layer = layer

    def forward(self, input_ids, attention_mask, token_type_ids):  # type: ignore[no-untyped-def]
        out = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            output_hidden_states=True,
        )
        return out.hidden_states[self.layer]  # [1, T_tok, 768]


def _export(
    module: torch.nn.Module,
    args: tuple,
    path: Path,
    input_names: list[str],
    output_names: list[str],
    dynamic_axes: dict,
    opset: int,
) -> None:
    kw = dict(
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes,
        opset_version=opset,
        do_constant_folding=True,
    )
    if "dynamo" in inspect.signature(torch.onnx.export).parameters:
        kw["dynamo"] = False  # torch 2.9+ 기본값이 dynamo=True → 기존 TorchScript 경로 사용
    torch.onnx.export(module, args, str(path), **kw)
    print(f"  wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/melo_onnx")
    ap.add_argument("--lang", default="KR")
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--quantize-bert", action="store_true")
    ap.add_argument(
        "--bert-only",
        action="store_true",
        help="gnyong VITS ONNX 를 쓰고 BERT ONNX 만 필요할 때",
    )
    a = ap.parse_args()

    from melo.api import TTS
    from melo.text.symbols import symbols
    from melo.utils import get_text_for_tts_infer
    from transformers import AutoModelForMaskedLM, AutoTokenizer

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lang = a.lang
    torch.manual_seed(0)

    print("[1/4] MeloTTS 로드")
    tts = TTS(language=lang, device="cpu")
    model, hps = tts.model.eval(), tts.hps

    print("[2/4] VITS 합성기 내보내기" + (" (건너뜀: --bert-only)" if a.bert_only else ""))
    bert, ja_bert, phones, tones, lang_ids = get_text_for_tts_infer(
        SAMPLE_TEXT[lang], lang, hps, "cpu", tts.symbol_to_id
    )
    x = phones.unsqueeze(0)
    args = (
        x,
        torch.LongTensor([x.shape[1]]),
        torch.LongTensor([0]),
        tones.unsqueeze(0),
        lang_ids.unsqueeze(0),
        bert.unsqueeze(0),
        ja_bert.unsqueeze(0),
        torch.tensor([0.6]),
        torch.tensor([1.0]),
        torch.tensor([0.8]),
        torch.tensor([0.2]),
    )
    names = [
        "x",
        "x_lengths",
        "sid",
        "tones",
        "lang_ids",
        "bert",
        "ja_bert",
        "noise_scale",
        "length_scale",
        "noise_scale_w",
        "sdp_ratio",
    ]
    if not a.bert_only:
        with torch.no_grad():
            _export(
                VitsWrapper(model),
                args,
                out / f"melo_{lang.lower()}.onnx",
                names,
                ["audio"],
                {
                    "x": {1: "n"},
                    "tones": {1: "n"},
                    "lang_ids": {1: "n"},
                    "bert": {2: "n"},
                    "ja_bert": {2: "n"},
                    "audio": {2: "t"},
                },
                a.opset,
            )

    print("[3/4] BERT 특징 추출기 내보내기")
    bert_id = BERT_IDS[lang]
    tok = AutoTokenizer.from_pretrained(bert_id)
    tok.save_pretrained(out / "tokenizer")
    bert_model = AutoModelForMaskedLM.from_pretrained(bert_id).eval()
    enc = tok(SAMPLE_TEXT[lang], return_tensors="pt")
    with torch.no_grad():
        _export(
            BertWrapper(bert_model),
            (enc["input_ids"], enc["attention_mask"], enc["token_type_ids"]),
            out / f"bert_{lang.lower()}.onnx",
            ["input_ids", "attention_mask", "token_type_ids"],
            ["hidden"],
            {
                "input_ids": {1: "t"},
                "attention_mask": {1: "t"},
                "token_type_ids": {1: "t"},
                "hidden": {1: "t"},
            },
            a.opset,
        )
    if a.quantize_bert:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(
            str(out / f"bert_{lang.lower()}.onnx"),
            str(out / f"bert_{lang.lower()}.int8.onnx"),
            weight_type=QuantType.QInt8,
        )
        print(f"  wrote bert_{lang.lower()}.int8.onnx")

    print("[4/4] meta.json")
    meta = {
        "format": 1,
        "language": lang,
        "sampling_rate": int(hps.data.sampling_rate),
        "add_blank": bool(hps.data.add_blank),
        "spk2id": dict(hps.data.spk2id),
        "symbols": list(symbols),
        "bert_model_id": bert_id,
        "bert_slot": "ja_bert" if lang != "ZH" else "bert",  # KR 은 ja_bert(768) 자리에 넣고 bert(1024)는 0
        "bert_dims": {"bert": int(bert.shape[0]), "ja_bert": int(ja_bert.shape[0])},
        "vits_inputs": names,
        "defaults": {"speed": 1.0, "sdp_ratio": 0.2, "noise_scale": 0.6, "noise_scale_w": 0.8},
        "opset": a.opset,
        "source": {
            "melo_checkpoint": f"myshell-ai/MeloTTS-{'Korean' if lang == 'KR' else lang}",
            "torch": torch.__version__,
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("완료:", out.resolve())


if __name__ == "__main__":
    main()
