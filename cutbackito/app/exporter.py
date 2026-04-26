"""Render an EditPlan into actual video files (vertical clips, etc.)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .chat_editor import Clip, EditPlan
from .ffmpeg_utils import to_vertical_clip, cut_segment
from .multicam_sync import SyncedSource
from .transcription import Transcript


_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_-]+")


def _slugify(text: str) -> str:
    slug = _SAFE_CHARS.sub("_", text.strip()).strip("_")
    return slug[:60] or "clip"


@dataclass
class ExportedClip:
    path: Path
    clip: Clip


def _pick_source(camera: str, sources: list[SyncedSource]) -> SyncedSource:
    if camera and camera != "auto":
        for s in sources:
            if s.name == camera:
                return s
    return max(sources, key=lambda s: s.confidence)


def _write_subtitle_for_window(
    transcript: Transcript,
    start: float,
    end: float,
    dst: Path,
) -> Path | None:
    """Write a clip-relative SRT for the [start, end) window, or None if empty."""
    lines: list[str] = []
    idx = 1
    for seg in transcript.segments:
        if seg.end < start or seg.start > end:
            continue
        rel_start = max(0.0, seg.start - start)
        rel_end = max(rel_start + 0.1, seg.end - start)

        def fmt(t: float) -> str:
            ms = int(round(t * 1000))
            h, ms = divmod(ms, 3_600_000)
            m, ms = divmod(ms, 60_000)
            s, ms = divmod(ms, 1_000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        lines.append(str(idx))
        lines.append(f"{fmt(rel_start)} --> {fmt(rel_end)}")
        lines.append(seg.text.strip())
        lines.append("")
        idx += 1

    if not lines:
        return None
    dst.write_text("\n".join(lines), encoding="utf-8")
    return dst


def export_plan(
    plan: EditPlan,
    sources: list[SyncedSource],
    transcript: Transcript,
    out_dir: Path,
    *,
    burn_subtitles: bool = True,
) -> list[ExportedClip]:
    """Render every clip in the plan to disk, returning the produced paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    subs_dir = out_dir / "subs"
    subs_dir.mkdir(exist_ok=True)

    exported: list[ExportedClip] = []
    for i, clip in enumerate(plan.clips, start=1):
        source = _pick_source(clip.camera, sources)
        local_start = max(0.0, clip.start - source.offset_seconds)
        local_end = max(local_start + 0.5, clip.end - source.offset_seconds)
        local_end = min(local_end, source.duration)

        slug = f"{i:02d}_{_slugify(clip.title)}"
        dst = out_dir / f"{slug}.mp4"

        sub_path: Path | None = None
        if burn_subtitles and not clip.caption:
            sub_path = _write_subtitle_for_window(
                transcript, clip.start, clip.end, subs_dir / f"{slug}.srt"
            )

        if clip.format == "vertical_9_16":
            to_vertical_clip(
                source.path,
                dst,
                local_start,
                local_end,
                burn_subtitle_path=sub_path,
            )
        else:
            cut_segment(source.path, dst, local_start, local_end, copy=False)

        exported.append(ExportedClip(path=dst, clip=clip))
    return exported
