"""Whisper-based transcription wrapper.

Uses `faster-whisper` for CPU-friendly inference (int8 by default). Returns a
flat list of word/segment objects with timestamps so we can drive both viral
clipping and subtitle burn-in.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .config import settings
from .ffmpeg_utils import extract_mono_pcm

_model = None


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass
class Transcript:
    language: str
    segments: list[Segment]

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "segments": [asdict(s) for s in self.segments],
        }

    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments)

    def to_srt(self) -> str:
        def fmt(t: float) -> str:
            ms = int(round(t * 1000))
            h, ms = divmod(ms, 3_600_000)
            m, ms = divmod(ms, 60_000)
            s, ms = divmod(ms, 1_000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        lines: list[str] = []
        for i, seg in enumerate(self.segments, start=1):
            lines.append(str(i))
            lines.append(f"{fmt(seg.start)} --> {fmt(seg.end)}")
            lines.append(seg.text.strip())
            lines.append("")
        return "\n".join(lines)


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model


def transcribe(media_path: Path, *, language: str | None = None) -> Transcript:
    """Transcribe a media file. Extracts mono 16k PCM first for stable input."""
    workspace = settings.workspace_dir / "transcripts"
    workspace.mkdir(parents=True, exist_ok=True)
    pcm_path = extract_mono_pcm(media_path, workspace / f"{media_path.stem}.wav", sample_rate=16_000)

    model = _get_model()
    segments_iter, info = model.transcribe(
        str(pcm_path),
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5,
    )
    segments = [
        Segment(start=float(s.start), end=float(s.end), text=s.text.strip())
        for s in segments_iter
    ]
    return Transcript(language=info.language, segments=segments)
