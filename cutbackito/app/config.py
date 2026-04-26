"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    workspace_dir: Path
    max_upload_mb: int
    claude_model: str
    claude_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        workspace = Path(os.getenv("WORKSPACE_DIR", "./workspace")).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        return cls(
            whisper_model=os.getenv("WHISPER_MODEL", "small"),
            whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
            whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            workspace_dir=workspace,
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "2048")),
            claude_model=os.getenv("CLAUDE_MODEL", ""),
            claude_timeout_seconds=int(os.getenv("CLAUDE_TIMEOUT_SECONDS", "300")),
        )


settings = Settings.from_env()
