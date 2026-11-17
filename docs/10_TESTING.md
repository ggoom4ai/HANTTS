# 10. 테스트 전략

## 1. 계층
| 계층 | 도구 | 대상 | 실행 |
|---|---|---|---|
| 단위 | pytest | schema, text(정규화·분할·사전), audio(병합·SRT), catalog, download | 매 커밋 |
| 프로토콜 | 엔진 워커 | describe/synthesize/shutdown 은 설치된 엔진으로 확인 | 스모크 |
| UI | pytest-qt | param_panel, 설치 대화상자 상태 전이, 배너 표시 | 매 커밋 |
| 엔진 스모크 (`-m slow`) | pytest | 실제 엔진 설치 레시피 + 합성 1회 | 야간/태그 |
| Windows 음성 (`-m windows`) | pytest (windows-latest 러너) | 음성 열거, 영어 음성 합성(러너에 한국어 음성이 없을 수 있음 → 있으면 한국어도) | 매 커밋(Windows CI) |
| 설치본 E2E | 수동 체크리스트 + (옵션) pywinauto | 클린 VM 설치·제거 | 릴리스 전 |

## 2. 엔진 스모크 판정 기준
- 출력 WAV 존재, 길이 > 0.3초, NaN/Inf 없음, 피크 < 1.0, 무음 비율 < 80%
- 한국어 지원 엔진: (옵션) Whisper 기반 CER 측정으로 회귀 감시 — 개발 PC에서만

## 3. 회귀 고정 데이터
- `tests/fixtures/ko_sentences.txt`: 숫자·날짜·영문 혼합·긴 문장·감탄/의문 포함 50문장
- `tests/text/cases_normalize.tsv`: 입력 \t 기대 출력 (200+)

## 4. 릴리스 수동 체크리스트 (요약)
- [ ] 관리자 아닌 계정에서 설치/실행/제거
- [ ] 경로에 한글·공백 포함된 사용자명(`C:\Users\홍 길동`)에서 엔진 설치·합성
- [ ] 프록시 환경에서 설치, 오프라인 팩 설치
- [ ] 설치 중 취소 → 재시도 → 정상
- [ ] 워커 강제 종료(작업 관리자) → 자동 복구
- [ ] 3개 엔진 모든 파라미터 체크리스트(각 파라미터 최소/최대값 결과 차이 청취)
- [ ] Windows 음성: 영어판 Windows(한국어 음성 없음)에서 NEEDS_VOICE 표시 → 설정 열기 / 자동 설치(UAC) → 재검사 후 사용 가능
- [ ] Windows 음성: OneCore ↔ SAPI 백엔드 전환, SSML 모드, 단어 단위 SRT
