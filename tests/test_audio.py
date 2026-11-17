from __future__ import annotations

from pathlib import Path

import numpy as np

from hantts.core.audio.pipeline import concat, encode, normalize_lufs, read_mono, resample, write_srt


def test_resample_concat_encode_roundtrip(tmp_path: Path) -> None:
    sr = 8000
    tone = np.sin(2 * np.pi * 440 * np.arange(sr, dtype=np.float32) / sr).astype(np.float32)
    up = resample(tone, sr, 16000)
    assert len(up) == 16000
    merged = concat([tone[:100], tone[:100]], sr, 100)
    assert len(merged) == 200 + int(sr * 0.1)
    path = tmp_path / "out.wav"
    encode(merged, sr, path)
    audio, got = read_mono(path)
    assert got == sr
    assert len(audio) == len(merged)


def test_short_clip_skips_lufs() -> None:
    audio = np.ones(100, dtype=np.float32) * 0.2
    out = normalize_lufs(audio, 16000, -16.0)
    assert np.allclose(out, audio)


def test_srt(tmp_path: Path) -> None:
    path = tmp_path / "a.srt"
    write_srt([(0.0, 1.25, "안녕")], path)
    text = path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,250" in text
    assert "안녕" in text
