"""Chat-driven video editing using Claude.

The user types something like "give me the 3 funniest moments as 30-second
vertical clips with captions". We feed Claude the multicam-synced transcript
plus a tool surface (`select_clips`, `pick_camera`, `transcribe_only`,
`done`) and let it return a structured edit plan we can execute with ffmpeg.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import anthropic

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
  questions answered, surprising claims, quotable lines, laughter cues in
  bracketed transcript notes.
- When unsure which camera, pick the one with the highest sync confidence,
  or "auto" to let the renderer choose.
- Always emit the `submit_edit_plan` tool exactly once at the end.
- Do not produce overlapping clips unless the user explicitly asks for it.
"""


SUBMIT_TOOL: dict[str, Any] = {
    "name": "submit_edit_plan",
    "description": "Final edit plan. Call this exactly once after analysis.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "One-paragraph rationale for the chosen clips.",
            },
            "clips": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "start": {"type": "number", "description": "Reference-timeline seconds"},
                        "end": {"type": "number"},
                        "camera": {
                            "type": "string",
                            "description": "Camera name from the metadata, or 'auto'.",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["vertical_9_16", "landscape_16_9"],
                        },
                        "caption": {
                            "type": "string",
                            "description": "Optional burned-in subtitle override; empty to use transcript.",
                        },
                    },
                    "required": ["title", "start", "end", "camera", "format"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "clips"],
        "additionalProperties": False,
    },
}


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


def _client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env or your environment "
            "to use chat editing."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


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


def plan_edit(
    instruction: str,
    transcript: Transcript,
    cameras: list[dict[str, Any]],
) -> EditPlan:
    """Ask Claude to translate a natural-language edit request into an EditPlan."""
    client = _client()

    context_block = (
        f"{_format_cameras(cameras)}\n\n{_format_transcript(transcript)}"
    )

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=[
            {"type": "text", "text": SYSTEM_PROMPT},
            {
                "type": "text",
                "text": context_block,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        tools=[SUBMIT_TOOL],
        tool_choice={"type": "tool", "name": "submit_edit_plan"},
        messages=[{"role": "user", "content": instruction}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_edit_plan":
            return EditPlan.from_tool_input(block.input)

    raise RuntimeError(
        "Claude did not return an edit plan. Raw response: "
        + json.dumps([b.model_dump() for b in response.content], default=str)
    )
