# 11. 라이선스 정리

> 법률 자문이 아니다. 상용 배포 전 반드시 전문가 검토를 받는다.

| 구성요소 | 라이선스 | 앱과의 관계 | 주의 |
|---|---|---|---|
| HanTTS 앱 코드 | (프로젝트 결정) | – | |
| PySide6 / Qt | LGPL-3.0 | 동적 링크(번들 dll) | Qt dll 교체 가능 형태 유지, 고지문 포함 |
| uv | MIT / Apache-2.0 | 번들 실행 파일 | 고지문 |
| MeloTTS | MIT | 사용자 PC에 런타임 설치, 별도 프로세스 | |
| Supertonic 3 가중치 | BigScience OpenRAIL-M | 동일 | **사용 제한 조항**(유해 용도 금지 등) → 설치 시 동의, 생성물 이용 조건 안내 |
| Windows 음성 (OneCore/SAPI 엔진·음성) | Windows 라이선스 | OS 구성요소, 앱은 재배포하지 않음 | **생성 음성의 상업적 이용 조건은 Windows 라이선스 확인 필요** → 엔진 카드에 안내 |
| PyWinRT (`winrt-*`) | MIT | 앱 번들 | 고지문 |
| comtypes | MIT | 앱 번들 | 고지문 |
| 서드파티 SAPI 음성 | 각 제품 라이선스 | 사용자가 직접 설치 | 앱은 목록에 보여줄 뿐, 라이선스는 사용자 책임 안내 |

## 앱 내 처리
1. 엔진 설치 대화상자에서 `requires_consent` 라이선스는 체크박스 동의 필수, 동의 기록(엔진 id, 라이선스, 시각)을 DB에 저장. Supertonic의 BigScience OpenRAIL-M, MeloTTS의 MIT와 kykim BERT는 `default_checked`로 처음부터 체크되어 있다.
2. 설정 > 정보 > "오픈소스 라이선스" 화면에 앱 번들 + 설치된 엔진의 라이선스 목록 표시
3. 출력 파일 메타데이터(옵션)에 엔진/음성 이름 기록
4. "상업적 용도로 사용" 토글: 켜면 Windows 음성 카드에 상업 이용 조건 확인 안내를 강조
