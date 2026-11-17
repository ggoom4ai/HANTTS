# 06. 호스트 ↔ 워커 프로토콜

## 1. 전송
- 워커 실행: `<venv>\Scripts\python.exe -X utf8 -m hantts.worker.main --engine <id> --models-dir <dir> --threads <n>`
- **stdin/stdout = UTF-8 NDJSON** (한 줄에 JSON 하나). stdout에는 프로토콜 메시지 외 출력 금지
  → 워커 시작 직후 `sys.stdout`을 프로토콜 전용 핸들로 바꾸고, 기존 `print`/라이브러리 출력은 stderr로 리다이렉트.
- stderr = 로그(호스트가 `logs\worker-<id>.log`로 기록)
- 오디오는 파일로 교환: 호스트가 `out_path`를 지정, 워커가 그 경로에 WAV(float32) 저장.

## 2. 메시지 형식 (JSON-RPC 2.0 축약)
```jsonc
// 요청 (host → worker)
{"id": 7, "method": "synthesize", "params": {...}}
// 응답 (worker → host)
{"id": 7, "result": {...}}
{"id": 7, "error": {"code": "UNSUPPORTED_LANGUAGE", "message": "no installed Windows voice for 'ko-KR'", "data": {}}}
// 이벤트 (worker → host, id 없음 또는 관련 요청 id 포함)
{"event": "ready", "data": {"engine": "supertonic", "worker_version": "0.1.0", "pid": 1234}}
{"event": "progress", "id": 7, "data": {"stage": "synthesizing", "fraction": 0.4}}
{"event": "chunk", "id": 7, "data": {"path": "...\\c0003.wav", "index": 3, "duration": 1.82}}   // 스트리밍
{"event": "log", "data": {"level": "warning", "message": "..."}}
```

## 3. 메서드
| method | params | result | 설명 |
|---|---|---|---|
| `ping` | – | `{"pong": true}` | 헬스체크(30초 주기) |
| `describe` | – | `CapabilitySchema` | 모델 로드 없이 가능한 범위 + 로드 후 동적 항목(화자 등)은 `load` 이후 갱신 |
| `load` | `{"preload_voices": [...]}` | `{"load_seconds": 3.1}` | 모델 메모리 적재 |
| `synthesize` | `SynthRequest` | `SynthResult` | 단일 청크 합성 |
| `synthesize_batch` | `{"items":[SynthRequest...]}` | `{"items":[SynthResult...]}` | `features.batch`인 엔진만 |
| `cancel` | `{"target_id": 7}` | `{"cancelled": true}` | 스트리밍/배치 중단 (협조적 취소) |
| `list_voices` | `{"lang": "ko"}` | `{"voices":[VoiceSpec...]}` | 동적 음성 목록 (Windows에 설치된 음성 등) |
| `import_voice` | `{"path": "..."}` | `VoiceSpec` | 사용자 음성 가져오기 |
| `shutdown` | – | `{}` | 정상 종료 |

## 4. 데이터 구조 (`src/hantts/core/schema.py`가 단일 진실 원천)

```jsonc
// CapabilitySchema
{
  "engine_id": "supertonic",
  "display_name": "Supertonic 3",
  "engine_version": "3.0.0",
  "sample_rate": 44100,
  "languages": [{"code": "ko", "label_ko": "한국어", "support": "official"}, ...],
  "voices": [{"id": "F1", "label": "F1 (여성)", "langs": ["*"], "gender": "female", "preview_text": "안녕하세요"}],
  "params": [
    {"key": "speed", "type": "float", "label_ko": "속도", "help_ko": "1.0이 기본 속도입니다.",
     "default": 1.0, "min": 0.7, "max": 1.5, "step": 0.05, "unit": "x", "group": "basic", "order": 10},
    {"key": "total_steps", "type": "int", "label_ko": "품질 스텝", "default": 5, "min": 1, "max": 20,
     "group": "advanced", "order": 20}
  ],
  "features": {
    "streaming": false, "batch": true, "phoneme_input": false, "inline_pronunciation": false,
    "voice_blend": false, "custom_voice_import": true, "word_timestamps": false,
    "builtin_normalization": true
  },
  "limits": {"max_chars_per_request": 300, "ideal_chunk_seconds": [2, 20]}
}

// SynthRequest
{"text": "안녕하세요.", "lang": "ko", "voice": "F1", "params": {"speed": 0.95},
 "out_path": "C:\\...\\tmp\\session-1\\c0001.wav", "stream": false, "seed": null}

// SynthResult
{"path": "...c0001.wav", "sample_rate": 44100, "duration": 1.23, "elapsed": 0.08,
 "rtf": 0.065, "word_timestamps": null}
```

## 5. 오류 코드
| code | 의미 | 호스트 처리 |
|---|---|---|
| `NOT_LOADED` | load 전 synthesize | 자동 load 후 재시도 |
| `INVALID_PARAMS` | 스키마 위반 | 사용자에게 필드 하이라이트 |
| `UNSUPPORTED_LANGUAGE` | 언어 미지원 | 엔진 전환 제안 배너 |
| `VOICE_NOT_FOUND` | 음성 없음 | 음성 목록 새로고침 |
| `TEXT_TOO_LONG` | 청크 초과 | 분할기 재분할 |
| `CANCELLED` | 취소됨 | 조용히 종료 |
| `ENGINE_ERROR` | 엔진 내부 예외 (traceback은 `data`) | 오류 대화상자 + 로그 링크 |
| `OOM` | 메모리 부족 | 스레드/청크 축소 제안 |

## 6. 버전 호환
- `ready` 이벤트의 `worker_version`이 호스트 기대 범위(`>=x.y,<x+1`) 밖이면 호스트가 워커 휠 재설치 유도.
- 스키마 필드 추가는 하위 호환(무시 가능), 제거/의미 변경은 major 증가.
