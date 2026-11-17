"""영어 UI. 소스 문자열은 한국어이고, en 일 때만 이 표를 쓴다."""

from __future__ import annotations

from PySide6.QtCore import QTranslator

EN: dict[str, str] = {
    "작업": "Workspace",
    "엔진": "Engines",
    "사전": "Dictionary",
    "기록": "History",
    "설정": "Settings",
    "원고": "Script",
    "음성": "Voice",
    "기본": "Basic",
    "고급": "Advanced",
    "미리듣기": "Preview",
    "전체 생성": "Generate",
    "중지": "Stop",
    "내보내기": "Export",
    "파일 열기": "Open",
    "프리셋 저장": "Save preset",
    "기본값 복원": "Reset",
    "숫자·날짜 읽기 변환": "Read numbers and dates",
    "SRT 자막": "SRT subtitles",
    "설치": "Install",
    "제거": "Remove",
    "복구": "Repair",
    "테스트": "Test",
    "취소": "Cancel",
    "닫기": "Close",
    "다음": "Next",
    "이전": "Back",
    "건너뛰기": "Skip",
    "언어": "Language",
    "프리셋": "Preset",
    "샘플 듣기": "Preview voice",
    "변환 결과 미리보기": "Show normalized text",
    "오프라인 팩 가져오기": "Import offline pack",
    "캐시 정리": "Clear cache",
    "엔진이 알려준 파라미터로 자동 구성": "Built from the engine schema",
    "이 PC에 한국어 Windows 음성이 없습니다.": "This PC has no Korean Windows voice.",
    "Windows 설정에서 설치": "Install in Windows Settings",
    "자동 설치": "Install automatically",
    "음성 목록": "Voice list",
    "음성 목록 · %1": "Voice list · %1",
    "Windows 음성 목록": "Windows voices",
    "음성을 확인하고 있습니다.": "Looking up installed voices.",
    "설치된 음성이 없습니다.": "No voices are installed.",
    "음성 %1개": "%1 voices",
    "다시 시도": "Retry",
    "추가": "Add",
    "삭제": "Delete",
    "선택삭제": "Delete selected",
    "전체 삭제": "Delete all",
    "생성 기록을 모두 삭제할까요?": "Delete all generated history?",
    "저장": "Save",
}


class EnTranslator(QTranslator):
    def translate(self, context: str, source: str, disambiguation: str | None = None, n: int = -1) -> str:
        del context, disambiguation, n
        return EN.get(source, "")
