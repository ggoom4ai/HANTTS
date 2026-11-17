# Phase 0 스파이크 기록

이 문서는 엔진 API와 모델 해시를 어디서 확인했는지 적는다. 설치 머신에서 다시 돌릴 스크립트는 `spikes/`에 있다.

## 확인한 것

- Supertonic SDK 1.3.1: `TTS(model="supertonic-3", model_dir=, auto_download=False, intra_op_num_threads=, inter_op_num_threads=)`, `get_voice_style`, `get_voice_style_from_path`, `synthesize(..., total_steps=8, speed, silence_duration, lang, verbose=False)`. `text_normalization`은 SDK 인자가 아니다.
- MeloTTS 커밋 `209145371cff8fc3bd60d7be902ea69cbdb7965a`: `TTS(language=, device='cpu')`, `tts_to_file(..., sdp_ratio, noise_scale, noise_scale_w, speed, quiet=True)`. 내부 문장 분할은 항상 수행된다. 샘플 레이트는 `model.hps.data.sampling_rate`.
- Supertonic 자산 17개의 SHA256은 `engines/catalog/catalog.json`에 있다. 큰 ONNX는 Hugging Face LFS oid를 썼고, 작은 JSON은 파일을 받아 계산했다.
- uv 0.13.8 Windows zip SHA256은 GitHub 릴리스 asset digest `529e78a9cec6cd7e3e014f7ecd8bda0c113969d4ed0f2efeedb85c30943325b8`이다. zip 파일을 다시 받아 대조하지는 않았다.

## 이 PC에서 확인한 Windows 음성

`spikes/windows_voices.py`로 OneCore 목록을 읽었다. 한국어 음성은 Microsoft Heami (`ko-KR`)가 있다. 그 음성으로 `안녕하세요. 2026년 11월 16일입니다.`를 합성하면 16kHz WAV가 나오고, 이번 측정에서 길이는 5.11초, RTF는 0.085였다. 단어 경계 메타데이터는 빈 목록으로 돌아와 자막 타임스탬프는 문장 단위로만 남는다.

## 아직 이 환경에서 실행하지 않은 것

- Supertonic, MeloTTS의 실제 venv 설치와 청취 벤치 (`spikes/install_*.ps1`, `spikes/bench.py`).
- `spikes/introspect.py`를 설치된 venv 안에서 돌려 `spikes/introspect-supertonic.json`, `spikes/introspect-melo.json`을 채우는 일. 지금은 패키지가 없어 `missing`만 기록되어 있다.
- SAPI 음성 목록, SSML, 내레이터 자연 음성(InJoon, SunHi) 노출 여부.
