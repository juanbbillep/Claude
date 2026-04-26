"""Multicam audio sync via FFT cross-correlation.

Given N video/audio sources, we extract a low-rate mono PCM track from each,
cross-correlate against a reference, and recover the per-source offset (in
seconds) that aligns them to a common timeline.

For each source, returns `offset_seconds` = the reference-timeline timestamp
at which the source's local t=0 occurs. So a positive offset means the source
starts AFTER the reference; a negative offset means the source starts BEFORE
the reference. Conversion: `t_local = t_reference - offset_seconds`.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.signal import correlate, correlation_lags

from .ffmpeg_utils import extract_mono_pcm, probe

SYNC_SAMPLE_RATE = 8_000  # plenty for cross-correlation, keeps memory low


@dataclass
class SyncedSource:
    name: str
    path: Path
    duration: float
    offset_seconds: float
    confidence: float


def _read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sr


def _normalize(x: np.ndarray) -> np.ndarray:
    x = x - x.mean()
    peak = float(np.max(np.abs(x))) or 1.0
    return x / peak


def _xcorr_offset(ref: np.ndarray, other: np.ndarray, sample_rate: int) -> tuple[float, float]:
    """Return (offset_seconds, confidence in [0, 1])."""
    ref_n = _normalize(ref)
    other_n = _normalize(other)
    corr = correlate(ref_n, other_n, mode="full", method="fft")
    lags = correlation_lags(len(ref_n), len(other_n), mode="full")
    peak_idx = int(np.argmax(np.abs(corr)))
    lag = int(lags[peak_idx])
    offset_seconds = lag / sample_rate
    peak_value = float(abs(corr[peak_idx]))
    energy = float(np.sqrt(np.dot(ref_n, ref_n) * np.dot(other_n, other_n))) or 1.0
    confidence = max(0.0, min(1.0, peak_value / energy))
    return offset_seconds, confidence


def sync_sources(
    sources: list[Path],
    workspace: Path,
    *,
    reference_index: int = 0,
) -> list[SyncedSource]:
    """Compute offsets that align every source to `sources[reference_index]`.

    `offset_seconds` is the reference-timeline timestamp at which the source's
    local t=0 lands. To seek a reference-time `t` inside `source`, use
    `t - source.offset_seconds`.
    """
    if not sources:
        return []

    workspace.mkdir(parents=True, exist_ok=True)
    pcm_dir = workspace / "sync_pcm"
    pcm_dir.mkdir(exist_ok=True)

    pcm_paths: list[Path] = []
    durations: list[float] = []
    for src in sources:
        info = probe(src)
        if not info.has_audio:
            raise ValueError(f"Source has no audio track: {src}")
        durations.append(info.duration)
        pcm_paths.append(
            extract_mono_pcm(src, pcm_dir / f"{src.stem}.wav", sample_rate=SYNC_SAMPLE_RATE)
        )

    ref_samples, sr = _read_wav_mono(pcm_paths[reference_index])

    results: list[SyncedSource] = []
    for i, (src, pcm) in enumerate(zip(sources, pcm_paths)):
        if i == reference_index:
            results.append(
                SyncedSource(
                    name=src.stem,
                    path=src,
                    duration=durations[i],
                    offset_seconds=0.0,
                    confidence=1.0,
                )
            )
            continue
        other_samples, other_sr = _read_wav_mono(pcm)
        if other_sr != sr:
            raise ValueError(f"Sample rate mismatch on {src}: {other_sr} vs {sr}")
        offset, confidence = _xcorr_offset(ref_samples, other_samples, sr)
        results.append(
            SyncedSource(
                name=src.stem,
                path=src,
                duration=durations[i],
                offset_seconds=offset,
                confidence=confidence,
            )
        )
    return results


def common_window(synced: list[SyncedSource]) -> tuple[float, float]:
    """Compute the [start, end) window where all sources overlap, in reference time."""
    if not synced:
        return (0.0, 0.0)
    starts = [s.offset_seconds for s in synced]
    ends = [s.offset_seconds + s.duration for s in synced]
    return (max(starts), min(ends))
