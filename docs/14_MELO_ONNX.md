# 14. MeloTTS ONNX 전환

> 목표: 사용자 PC의 MeloTTS 엔진에서 **PyTorch를 없애고 ONNX Runtime으로 실행**한다.
> 효과(예상, Phase 0에서 실측): 설치 용량 약 2.1GB → 수백 MB, Python 3.10 고정 해제(3.11 통일), Windows 설치 문제(torch·unidic) 제거.
> 엔진이 노출하는 기능(speed, sdp_ratio, noise_scale, noise_scale_w, 화자)은 **그대로 유지**한다 — 모두 ONNX 입력으로 남긴다.

**현재 채택:** gnyong `melotts_kr_fp32.onnx`(커밋 `c11013196ea7efe6ee06b418ec679212770533f7`). BERT 특징은 0이고 `vocab.txt`는 어절 정렬에만 쓴다. 음소 ID는 `melotts_kr_config.json`의 `symbols` 순서다. int8과 PyTorch 경로는 쓰지 않는다.

## 1. 현황과 결정
- MyShell은 한국어 MeloTTS의 **공식 ONNX 배포본을 내지 않는다.** (공식 저장소에 ONNX 내보내기 PR #276이 있으나 기본 기능 아님)
- **1순위 출처: 커뮤니티 변환본 [`gnyong/melotts-kr-onnx`](https://huggingface.co/gnyong/melotts-kr-onnx)** (MIT, 원본 `myshell-ai/MeloTTS-Korean`) — §2.
- **2순위(대안): 직접 변환** — §3 스크립트. gnyong 변환본이 검증을 통과하지 못하거나 저장소가 사라졌을 때 사용.
- 어느 쪽이든 최종 파일은 **우리 GitHub Release에 미러**하고 SHA256으로 고정해 앱이 내려받게 한다 (개인 저장소는 사라질 수 있음).
- 한국어 BERT(`kykim/bert-kor-base`)를 쓰게 될 경우 그 라이선스는 별도 확인 🔍.

## 1.5 MeloTTS 한국어 추론 구조 (무엇을 ONNX로 바꾸나)

```
원문 ─▶ ① 텍스트 프런트엔드 (순수 Python, torch 불필요)
         korean.text_normalize → 어절 단위 g2pkk 발음 변환 → jamo 분해 → 음소(phones)·성조(tones)·word2ph
      ─▶ ② BERT 특징 (torch 사용 ★) kykim/bert-kor-base, hidden_states[-3] → word2ph만큼 반복 → [768, n]
      ─▶ ③ VITS 합성기 (torch 사용 ★) SynthesizerTrn.infer(x, tones, lang_ids, bert(0), ja_bert, sid, …) → 파형
```
- ★ 두 곳을 ONNX로 바꾼다: 합성기는 gnyong 변환본(`melotts_kr_*.onnx`) 또는 직접 변환한 `melo_kr.onnx`, BERT는 필요할 때만 `bert_kr.onnx`.
- 한국어는 BERT 특징을 `ja_bert`(768차원) 자리에 넣고 `bert`(1024차원)는 0으로 채운다 (melo `get_text_for_tts_infer` 동작). `meta.json`의 `bert_slot`에 기록.
- ①은 MeloTTS 코드를 **앱으로 옮겨(vendoring)** torch 없이 돌린다 (MIT 고지 유지).

## 2. gnyong/melotts-kr-onnx 사용 (1순위)

### 2.1 저장소 내용 (2026-11-16 확인)
| 파일 | 크기 | SHA256 (manifest.json) | 비고 |
|---|---|---|---|
| `melotts_kr_fp32.onnx` | 170,506,511 B | `a2450570…e2220e9` | 기준 정확도 |
| `melotts_kr_fp16.onnx` | 86,862,921 B | `0d186c0b…cc6288b5` | GPU/NPU용 — CPU에선 이점 적음 |
| `melotts_kr_int8.onnx` | 53,465,508 B | `421b94ce…fc860f88` | 합성기 전체 동적 int8 → **음질 청취 필수** |
| `melotts_kr_fp16_no_bert.onnx` | 약 86 MB | (manifest에 없음 → 직접 계산) | BERT 투영층을 0으로 만든 판 |
| `symbols.json` | 9,645 B | `bf8d22ee…919ae3b`* | 성조·언어 맵. `symbol_to_id`는 원본 `symbols.py` 순서라 합성 ID로 쓰지 않는다 |
| `melotts_kr_config.json` | 3,405 B | `74543376…1fd7695c` | 44,100Hz, add_blank=true, spk2id `{"KR":0}`, 심볼 219개 |
| `g2pkk.tar.gz` / `mecab_ko_dic.tar.gz` | 18 KB / 34 MB | manifest 참고 | 전처리 자료. mecab 사전은 네이티브 mecab 필요 |
\* 전체 해시는 `tools/melo_onnx/compare_gnyong.py`의 `SHA256` 표와 manifest.json 참고.

- 변환 당시 버전: melotts 0.1.2, g2pkk 0.1.2, python-mecab-ko 1.3.7, python-mecab-ko-dic 2.1.1.post2 (manifest).
- ONNX 입력: `x, x_lengths, sid, tone, language, bert[1,1024,T], ja_bert[1,768,T], noise_scale, length_scale, noise_scale_w, sdp_ratio` → `audio` (44.1kHz). 우리 변환 스크립트와 같은 구조라 **모든 파라미터를 그대로 노출**할 수 있다.
- 최신 커밋 `c11013196ea7efe6ee06b418ec679212770533f7`(fp16_no_bert 추가). 앱 카탈로그는 이 해시로 고정한다(`resolve/main` 금지). 자체 Release 미러는 아직 없다.
- **음소 ID는 `melotts_kr_config.json`의 `symbols` 순서다.** 두 목록의 집합은 같지만 순서가 다르고, 한국어 자모·문장 부호는 config 인덱스가 `symbols.json`보다 2 크다. `우리는`(우리는)을 `symbols.json` ID로 넣으면 임베딩이 `쇠드귀`로 읽는다. 언어 ID(KR=4)와 성조 시작(KR=11)만 `symbols.json`을 쓴다.

### 2.2 확인해야 할 점
1. **BERT를 0으로 넣는 방식:** 모델 카드는 한국어일 때 `bert`·`ja_bert`를 0으로 넣으라고 안내한다. 원본 MeloTTS는 한국어 BERT 특징을 `ja_bert`에 넣어 억양을 만든다 → 0으로 넣으면 억양이 단조로워질 수 있다. **비교 청취로 결정** (§2.3).
2. **검증 자료 없음:** 정확도·속도 평가, 변환 스크립트가 공개되어 있지 않다 → 우리가 노이즈 0 조건에서 원본과 파형을 비교해 변환이 맞는지 확인한다.
3. **텍스트 전처리 미포함:** g2pkk는 **mecab-ko를 사용**한다(manifest). Windows에서 `python-mecab-ko` 휠이 설치되는지 확인 🔍. 안 되면 mecab 없이 동작하도록 전처리를 수정하거나 사전 기반 대체 경로 검토.
4. **int8 음질:** 합성기 전체를 양자화한 판이라 fp32와 비교 청취.

### 2.3 비교 절차 (T0.6)
변환 환경(§3의 `build\melo-export`, PyTorch MeloTTS 설치됨)에서:
```powershell
& $py -m pip install huggingface_hub
& $py tools\melo_onnx\compare_gnyong.py --revision <전체 커밋 해시> --model fp32 --out build\melo_compare
& $py tools\melo_onnx\compare_gnyong.py --revision <전체 커밋 해시> --model int8 --out build\melo_compare
```
문장마다 세 가지 wav와 `summary.csv`(길이, RTF, 노이즈 0 최대 차이)를 만든다.

| 기호 | 방식 | 의미 |
|---|---|---|
| a | 원본 PyTorch | 기준 |
| b | gnyong ONNX + 실제 BERT 특징(`ja_bert`) | 원본과 같은 입력 — 변환 정확도와 음질 확인 |
| c | gnyong ONNX + BERT 0 | 모델 카드 방식 — BERT 없이 충분한지 확인 |

**판정 기준과 결정**
| 결과 | 결정 |
|---|---|
| 노이즈 0 최대 차이가 큼(> 1e-2) 또는 b가 a와 다르게 들림 | gnyong 변환본 폐기 → §3 직접 변환 |
| c가 a·b와 거의 구분되지 않음 | **BERT 없이 배포** — 엔진에 BERT·토크나이저 불필요(가장 작고 단순). `bert`·`ja_bert`는 0 입력 |
| c가 확실히 단조로움, b는 a와 같음 | **gnyong ONNX + 우리 BERT ONNX** — `export_melo_onnx.py --bert-only`로 `bert_kr(.int8).onnx`만 만들어 함께 배포 |
| int8이 fp32와 구분되지 않음 | int8(53MB) 채택, 아니면 fp32(171MB) |

결과와 판정은 `docs/spike_report.md`에 기록하고, 채택한 파일을 자체 Release에 올린 뒤 `catalog.json`의 melo `assets`를 확정한다.

## 3. 직접 변환 (2순위 / BERT만 필요할 때)

BERT ONNX만 필요하면 `--bert-only`를 붙인다.


```powershell
# 변환 전용 환경 — 앱/엔진 환경과 별개
uv venv build\melo-export --python 3.10
$py = "build\melo-export\Scripts\python.exe"
uv pip install --python $py torch --index-url https://download.pytorch.org/whl/cpu
uv pip install --python $py "git+https://github.com/myshell-ai/MeloTTS@<고정 커밋>" onnx onnxruntime soundfile
& $py -m unidic download          # melo import 시 필요할 수 있음

& $py tools\melo_onnx\export_melo_onnx.py --out build\melo_onnx --lang KR --quantize-bert
& $py tools\melo_onnx\verify_melo_onnx.py --dir build\melo_onnx --lang KR
```

| 산출물 | 내용 |
|---|---|
| `melo_kr.onnx` | VITS 합성기. 입력: `x, x_lengths, sid, tones, lang_ids, bert, ja_bert, noise_scale, length_scale, noise_scale_w, sdp_ratio` → 출력 `audio [1,1,T]` |
| `bert_kr.onnx` / `bert_kr.int8.onnx` | BERT 특징 추출기(fp32 / int8 동적 양자화). 출력 `hidden [1, 토큰수, 768]` |
| `tokenizer/` | BERT 토크나이저 파일 (`tokenizers` 라이브러리로 읽음) |
| `meta.json` | 샘플레이트, add_blank, spk2id, 심볼 표, 입력 순서, 기본 파라미터 |

**검증 기준** (`verify_melo_onnx.py`)
- 노이즈 0 조건에서 PyTorch와 ONNX 파형 길이가 같고 최대 차이가 작아야 한다(목표 1e-3 이하).
- `verify/onnx_*.wav`를 직접 들어 원본과 차이가 없는지 확인.
- BERT int8은 특징값이 조금 달라진다 → fp32와 int8로 각각 합성해 들어보고 채택 여부 결정. VITS 합성기는 int8 양자화하지 않는다(음질 저하 위험).

**변환 시 흔한 문제**
- `torch.onnx.export` 오류: torch 2.9 이상은 기본값이 dynamo 경로라 스크립트에서 `dynamo=False`로 고정해 두었다. 그래도 실패하면 torch 2.4–2.6 대에서 변환.
- 입력 길이 고정 문제: 짧은/긴 문장 모두 돌려 보고, 길이가 바뀌면 오류가 나는지 확인(동적 축 `n`, `t`).
- 무작위성: VITS는 노이즈를 쓰므로 같은 입력도 매번 조금 다르다 — 정상. 비교는 노이즈 0으로.

## 4. 앱(엔진 워커)에서 ONNX로 추론하기

엔진 환경 패키지(잠금 파일 `locks/melo-win_amd64.txt`): `onnxruntime`, `numpy`, `g2pkk`, `python-mecab-ko`(+사전), `jamo`, `anyascii` (+ `soundfile`, 워커 휠), BERT를 쓰는 경우에만 `tokenizers`. **torch·transformers 없음.** 🔍 `python-mecab-ko`의 Windows 휠 설치 여부를 Phase 0에서 확인.

BERT 없이 배포하기로 결정하면(§2.3) 아래 2단계를 건너뛰고 `bert`·`ja_bert`에 0을 넣는다.

1. **프런트엔드 이식** → `src/hantts/engines/melo_frontend/`
   - MeloTTS의 `melo/text/korean.py`, `ko_dictionary.py`, `symbols.py`, `cleaned_text_to_sequence`, `commons.intersperse`를 옮긴다(파일 머리에 MIT 고지).
   - torch·transformers import를 제거하고, 단어 분리에 쓰던 `AutoTokenizer`는 `tokenizers.Tokenizer.from_file("tokenizer/tokenizer.json")`로 바꾼다.
   - 출력: `phones, tones, lang_ids, word2ph` (numpy int64), `add_blank`이면 음소·성조·언어 열에 0을 끼워 넣고 `word2ph` 각 값을 2배, 첫 값에 +1 (melo와 동일).
2. **BERT 특징**: `bert_kr(.int8).onnx` 실행 → `hidden[0]`을 `word2ph`만큼 `np.repeat` → 전치해 `[768, n]`. `ja_bert`에 넣고 `bert`는 `zeros([1024, n])`.
3. **합성**: 음소 ID는 `melotts_kr_config.json`의 `symbols` 인덱스다(§2.1). `melo_kr.onnx`에 넣고, 파라미터는 `length_scale = 1/speed`, 나머지는 그대로 float32 `[1]` 텐서로 반환한다.
4. **세션 설정**: `SessionOptions.intra_op_num_threads = 설정의 CPU 스레드`, `graph_optimization_level = ORT_ENABLE_ALL`, 세션은 워커 수명 동안 재사용.
5. **회귀 테스트**: `verify_melo_onnx.py`가 만든 PyTorch 기준 음소열·특징을 `tests/fixtures/melo_kr/*.npz`로 저장해 두고, 이식한 프런트엔드 출력이 같은지 비교(이 PC에 torch가 없어도 테스트 가능).

## 5. HanTTS 반영 사항
| 항목 | 변경 |
|---|---|
| `catalog.json` melo | `runtime: "onnx"`, `python: "3.11"`, torch 인덱스 제거, `assets` = gnyong 변환본(커밋 고정) → T0.6 판정 후 자체 Release 미러 URL을 첫 번째로, `post_install` 제거 |
| `03_ENGINES.md` §2 | 런타임 ONNX, 리스크 항목 갱신(Windows 설치 문제 해소, 변환 품질 검증 추가) |
| 어댑터 `engines/melo.py` | 위 4절 구조. `describe()`의 화자 목록은 `meta.json`의 `spk2id`에서 |
| 오프라인 팩 | torch가 빠져 팩 크기도 크게 감소 |
| 현재 런타임 | ONNX fp32만. PyTorch 경로와 int8 기본 모델은 현재 구성에 없다 |

## 6. 다른 언어
같은 스크립트로 `--lang EN|JP|ES|FR|ZH`도 변환할 수 있으나, 언어마다 BERT 모델과 프런트엔드(일본어 MeCab, 중국어 jieba 등)가 다르다. v1은 **KR만 ONNX**로 하고, 다른 언어가 필요하면 언어별로 같은 절차를 반복한다.
