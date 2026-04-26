"""Thin wrappers around ffmpeg/ffprobe that we reuse across the pipeline."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


class FFmpegError(RuntimeError):
    """Raised when ffmpeg or ffprobe exits non-zero."""


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    has_audio: bool
    has_video: bool
    width: int | None
    height: int | None
    fps: float | None
    sample_rate: int | None


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(f"{' '.join(cmd)}\n{result.stderr}")
    return result


def probe(path: Path) -> MediaInfo:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    raw = _run(cmd).stdout
    data = json.loads(raw)
    streams = data.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    video = next((s for s in streams if s.get("codec_type") == "video"), None)

    fps = None
    if video and "r_frame_rate" in video:
        num, _, den = video["r_frame_rate"].partition("/")
        try:
            fps = float(num) / float(den) if den and float(den) else float(num)
        except ValueError:
            fps = None

    duration = float(data.get("format", {}).get("duration", 0.0))
    return MediaInfo(
        duration=duration,
        has_audio=audio is not None,
        has_video=video is not None,
        width=int(video["width"]) if video and "width" in video else None,
        height=int(video["height"]) if video and "height" in video else None,
        fps=fps,
        sample_rate=int(audio["sample_rate"]) if audio and "sample_rate" in audio else None,
    )


def extract_mono_pcm(src: Path, dst: Path, sample_rate: int = 16_000) -> Path:
    """Extract a mono PCM WAV (used for sync + Whisper)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(dst),
        ]
    )
    return dst


def cut_segment(src: Path, dst: Path, start: float, end: float, *, copy: bool = True) -> Path:
    """Cut [start, end) from a source file. Stream-copy by default for speed."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.0, end - start)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(src),
        "-t",
        f"{duration:.3f}",
    ]
    if copy:
        cmd += ["-c", "copy"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac"]
    cmd.append(str(dst))
    _run(cmd)
    return dst


def concat_files(parts: list[Path], dst: Path) -> Path:
    """Concatenate using the demuxer (requires identical codecs)."""
    list_path = dst.with_suffix(".txt")
    list_path.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts))
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(dst),
        ]
    )
    list_path.unlink(missing_ok=True)
    return dst


def to_vertical_clip(
    src: Path,
    dst: Path,
    start: float,
    end: float,
    *,
    target_w: int = 1080,
    target_h: int = 1920,
    burn_subtitle_path: Path | None = None,
) -> Path:
    """Render a 9:16 viral clip. Center-crops, scales, optional subtitle burn-in."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.0, end - start)
    vf = (
        f"scale={target_w}:-2:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h}"
    )
    if burn_subtitle_path is not None:
        escaped = str(burn_subtitle_path).replace(":", r"\:").replace("'", r"\'")
        vf += f",subtitles='{escaped}':force_style='Alignment=2,Fontsize=24,Outline=2,BorderStyle=1'"
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(src),
            "-t",
            f"{duration:.3f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(dst),
        ]
    )
    return dst


def shift_and_pad(src: Path, dst: Path, offset: float, duration: float) -> Path:
    """Produce a copy of `src` aligned to a global timeline.

    Positive offset => prepend silence/black; negative offset => trim from start.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if offset >= 0:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-af",
            f"adelay={int(offset * 1000)}|{int(offset * 1000)}",
            "-vf",
            f"tpad=start_duration={offset:.3f}:start_mode=add:color=black",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            str(dst),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{-offset:.3f}",
            "-i",
            str(src),
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            str(dst),
        ]
    _run(cmd)
    return dst
