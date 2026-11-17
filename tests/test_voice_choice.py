from __future__ import annotations

from hantts.app.studio import voice_for_lang
from hantts.core.schema import VoiceSpec


def test_korean_replaces_stale_or_english_voice() -> None:
    voices = (
        VoiceSpec("david", "Microsoft David", langs=("en",)),
        VoiceSpec("heami", "Microsoft Heami", langs=("ko",)),
    )
    assert voice_for_lang(voices, "ko", "F5") == "heami"
    assert voice_for_lang(voices, "ko", "david") == "heami"
    assert voice_for_lang(voices, "ko", "heami") == "heami"
    assert voice_for_lang(voices, "en", "heami") == "david"
