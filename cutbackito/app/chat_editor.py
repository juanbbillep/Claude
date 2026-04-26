"""Chat-driven video editing via the Claude Code CLI (no API key needed).

Shells out to `claude -p` which authenticates against your Claude Pro/Max
subscription. Zero extra cost: the call is billed against your existing
Claude Code usage, not against an Anthropic API account.

Prerequisites:
    - Install Claude Code: https://claude.com/claude-code
    - Run `claude login` once on the host (or mount ~/.claude into Docker)
    - The `claude` binary must be on PATH for the user running this app.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from .config import settings
from .transcription import Transcript


SYSTEM_PROMPT = """You are Cutbackito, an AI video editor. You receive:
- A transcript with word-level timestamps from a multicam shoot.
- Metadata about the available cameras (names, durations, sync offsets).
- A natural-language instruction from the user.

Your job is to translate the instruction into an EDIT PLAN: a list of clips,
each with start/end timestamps in the REFERENCE TIMELINE (seconds), the
preferred camera angle, an export format (`vertical_9_16` for viral / OpusClip
style, or `landscape_16_9`), and a short caption / title.

Guidelines:
- Use real timestamps from the transcript. Never invent.
- Default viral clip length is 20-60 seconds. Strict max 90 seconds.
- For "best moments" / "highlights", look for: emotional peaks, punchlines,
  questions answered, surprising claims, quotable lines, laughter cues.
- When unsure which camera, pick the one with the highest sync confidence,
  or "auto" to let the renderer choose.
- Do not produce overlapping clips unless the user explicitly asks for it.
"""


JSON_INSTRUCTIONS = """
RESPONSE FORMAT — STRICT
========================
Reply with a single JSON object and NOTHING ELSE. No prose before or after.
No markdown fences. No comments. Exactly this shape:

{
  "summary": "one-paragraph rationale for the chosen clips",
  "clips": [
    {
      "title": "short slug for filename",
      "start": 12.0,
      "end": 42.0,
      "camera": "cam_a",
      "format": "vertical_9_16",
      "caption": ""
    }
  ]
}

Fields:
- "start"/"end": floats, seconds in the reference timeline
- "camera": one of the camera names from the metadata, or "auto"
- "format": "vertical_9_16" or "landscape_16_9"
- "caption": optional override; leave "" to burn the transcript instead
"""


@dataclass
class Clip:
    title: str
    start: float
    end: float
    camera: str
    format: str
    caption: str = ""


@dataclass
class EditPlan:
    summary: str
    clips: list[Clip]

    @classmethod
    def from_tool_input(cls, payload: dict[str, Any]) -> "EditPlan":
        return cls(
            summary=payload.get("summary", ""),
            clips=[
                Clip(
                    title=c["title"],
                    start=float(c["start"]),
                    end=float(c["end"]),
                    camera=c["camera"],
                    format=c["format"],
                    caption=c.get("caption", ""),
                )
                for c in payload.get("clips", [])
            ],
        )


def claude_cli_path() -> str | None:
    """Return the absolute path to the `claude` CLI, or None if missing."""
    return shutil.which("claude")


def _check_claude_installed() -> str:
    path = claude_cli_path()
    if not path:
        raise RuntimeError(
            "The `claude` CLI is not installed or not on PATH.\n"
            "Install Claude Code from https://claude.com/claude-code, "
            "run `claude login`, and make sure the `claude` binary is "
            "on PATH for the user running this app."
        )
    return path


def _format_cameras(cameras: list[dict[str, Any]]) -> str:
    lines = ["Available cameras (offsets in reference-timeline seconds):"]
    for cam in cameras:
        lines.append(
            f"- {cam['name']}: duration {cam['duration']:.1f}s, "
            f"offset {cam['offset_seconds']:+.3f}s, "
            f"sync confidence {cam['confidence']:.2f}"
        )
    return "\n".join(lines)


def _format_transcript(transcript: Transcript) -> str:
    lines = [f"Transcript (language: {transcript.language}):"]
    for seg in transcript.segments:
        lines.append(f"[{seg.start:7.2f} -> {seg.end:7.2f}] {seg.text}")
    return "\n".join(lines)


_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the assistant's reply as JSON, tolerating fences or stray prose."""
    text = text.strip()
    fenced = _FENCED_JSON.search(text)
    if fenced:
        text = fenced.group(1)
    elif not text.startswith("{"):
        i = text.find("{")
        if i >= 0:
            # Scan to the matching closing brace at depth 0
            depth = 0
            end = -1
            for j, ch in enumerate(text[i:], start=i):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
            if end > i:
                text = text[i:end]
    return json.loads(text)


def plan_edit(
    instruction: str,
    transcript: Transcript,
    cameras: list[dict[str, Any]],
) -> EditPlan:
    """Translate a natural-language edit request into an EditPlan via Claude Code."""
    cli = _check_claude_installed()

    full_prompt = "\n\n".join(
        [
            SYSTEM_PROMPT,
            _format_cameras(cameras),
            _format_transcript(transcript),
            f"USER INSTRUCTION: {instruction}",
            JSON_INSTRUCTIONS,
        ]
    )

    cmd = [cli, "-p", "--output-format", "text"]
    if settings.claude_model:
        cmd += ["--model", settings.claude_model]

    proc = subprocess.run(
        cmd,
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=settings.claude_timeout_seconds,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"`claude` CLI failed (exit {proc.returncode}). "
            f"stderr: {proc.stderr.strip() or '(empty)'}\n"
            f"stdout: {proc.stdout.strip()[:400] or '(empty)'}"
        )

    try:
        payload = _extract_json(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "Claude did not return valid JSON.\n"
            f"Parse error: {e}\n"
            f"Raw response (first 800 chars):\n{proc.stdout[:800]}"
        ) from e

    return EditPlan.from_tool_input(payload)
