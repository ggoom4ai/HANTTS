"""청크 병합, 리샘플, LUFS, 인코딩, SRT (docs/02_ARCHITECTURE.md §7.2)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

from hantts.core.errors import AudioError


def read_mono(path: Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return audio.mean(axis=1).astype(np.float32), int(sr)


def resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or len(audio) == 0:
        return audio
    out = soxr.resample(audio, src_sr, dst_sr)
    return np.asarray(out, dtype=np.float32)


def normalize_lufs(audio: np.ndarray, sr: int, target: float) -> np.ndarray:
    if len(audio) < int(sr * 0.4):
        return audio
    import pyloudnorm as pyln

    meter = pyln.Meter(sr)
    loud = float(meter.integrated_loudness(audio))
    if not np.isfinite(loud):
        return audio
    normalized = pyln.normalize.loudness(audio, loud, target)
    return np.asarray(normalized, dtype=np.float32)


def concat(parts: list[np.ndarray], sr: int, silence_ms: int) -> np.ndarray:
    if not parts:
        return np.zeros(0, dtype=np.float32)
    gap = np.zeros(max(0, int(sr * silence_ms / 1000)), dtype=np.float32)
    chunks: list[np.ndarray] = []
    for i, part in enumerate(parts):
        if i and len(gap):
            chunks.append(gap)
        chunks.append(part)
    return np.concatenate(chunks).astype(np.float32)


def encode(audio: np.ndarray, sr: int, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    formats = {".wav": "WAV", ".flac": "FLAC", ".ogg": "OGG", ".mp3": "MP3"}
    if ext not in formats:
        raise AudioError(f"지원하지 않는 형식입니다: {ext}")
    data = np.clip(np.nan_to_num(audio, nan=0.0), -1.0, 1.0).astype(np.float32)
    kwargs: dict[str, str] = {}
    if ext == ".ogg":
        kwargs["subtype"] = "VORBIS"
    try:
        sf.write(str(path), data, sr, format=formats[ext], **kwargs)
    except Exception as e:
        raise AudioError(f"오디오를 저장하지 못했습니다 ({ext}): {e}") from e


def write_srt(cues: list[tuple[float, float, str]], path: Path) -> None:
    lines: list[str] = []
    index = 1
    for start, end, text in cues:
        body = text.strip()
        if not body:
            continue
        lines.append(str(index))
        lines.append(f"{_ts(start)} --> {_ts(max(end, start + 0.05))}")
        lines.append(body)
        lines.append("")
        index += 1
    path.write_text("\n".join(lines), encoding="utf-8")


def render(
    chunk_paths: list[Path],
    *,
    silence_ms: int,
    target_sr: int,
    lufs: float | None,
    out_path: Path,
    cues: list[tuple[float, float, str]] | None = None,
) -> tuple[np.ndarray, int, float]:
    parts: list[np.ndarray] = []
    for path in chunk_paths:
        audio, sr = read_mono(path)
        parts.append(resample(audio, sr, target_sr))
    merged = concat(parts, target_sr, silence_ms)
    if lufs is not None and len(merged):
        merged = normalize_lufs(merged, target_sr, lufs)
    encode(merged, target_sr, out_path)
    if cues is not None:
        write_srt(cues, out_path.with_suffix(".srt"))
    duration = float(len(merged)) / float(target_sr) if target_sr else 0.0
    return merged, target_sr, duration


def _ts(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"
