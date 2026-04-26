"""Heuristic highlight detection over the transcript + audio energy.

Used as a fallback (and a fast preview) before the user fires up the LLM
chat editor. Picks segments with high lexical signal, laughter cues, and
audio peaks.
"""

from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .ffmpeg_utils import extract_mono_pcm
from .transcription import Transcript


LAUGH_CUES = re.compile(r"\[(?:laughs?|laughter|applause|cheering)\]", re.IGNORECASE)
QUESTION_RE = re.compile(r"\?")
QUOTABLE_HINTS = re.compile(
    r"\b(secret|never|always|crazy|incredible|honestly|the truth|my biggest)\b",
    re.IGNORECASE,
)


@dataclass
class Highlight:
    start: float
    end: float
    score: float
    reason: str
    text: str


def _audio_energy(media: Path, workspace: Path, hop_seconds: float = 0.5) -> tuple[np.ndarray, float]:
    pcm = extract_mono_pcm(media, workspace / f"{media.stem}_energy.wav", sample_rate=16_000)
    with wave.open(str(pcm), "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    hop = int(hop_seconds * sr)
    if hop <= 0:
        return np.zeros(0), hop_seconds
    n_frames = len(samples) // hop
    if n_frames == 0:
        return np.zeros(0), hop_seconds
    trimmed = samples[: n_frames * hop].reshape(n_frames, hop)
    rms = np.sqrt(np.mean(trimmed**2, axis=1))
    return rms, hop_seconds


def _segment_energy(rms: np.ndarray, hop_seconds: float, start: float, end: float) -> float:
    if rms.size == 0:
        return 0.0
    i0 = max(0, int(start / hop_seconds))
    i1 = min(rms.size, max(i0 + 1, int(end / hop_seconds)))
    window = rms[i0:i1]
    return float(window.mean()) if window.size else 0.0


def detect_highlights(
    transcript: Transcript,
    media: Path,
    workspace: Path,
    *,
    top_k: int = 5,
    target_seconds: float = 30.0,
) -> list[Highlight]:
    """Return up to `top_k` candidate highlight windows, ~`target_seconds` long each."""
    if not transcript.segments:
        return []

    rms, hop = _audio_energy(media, workspace)
    energy_max = float(rms.max()) if rms.size else 1.0

    scored: list[Highlight] = []
    for seg in transcript.segments:
        text = seg.text.strip()
        score = 0.0
        reasons: list[str] = []
        if LAUGH_CUES.search(text):
            score += 3.0
            reasons.append("laughter")
        if QUOTABLE_HINTS.search(text):
            score += 1.5
            reasons.append("quotable")
        if QUESTION_RE.search(text):
            score += 0.5
            reasons.append("question")
        words = len(text.split())
        if words >= 10:
            score += 0.5
            reasons.append("dense")
        e = _segment_energy(rms, hop, seg.start, seg.end) / (energy_max or 1.0)
        score += e * 1.5
        if e > 0.6:
            reasons.append("audio peak")
        if score <= 0:
            continue

        center = (seg.start + seg.end) / 2.0
        half = target_seconds / 2.0
        scored.append(
            Highlight(
                start=max(0.0, center - half),
                end=center + half,
                score=score,
                reason=", ".join(reasons) or "signal",
                text=text,
            )
        )

    scored.sort(key=lambda h: h.score, reverse=True)
    deduped: list[Highlight] = []
    for h in scored:
        if any(abs(h.start - existing.start) < target_seconds * 0.5 for existing in deduped):
            continue
        deduped.append(h)
        if len(deduped) >= top_k:
            break
    return deduped
