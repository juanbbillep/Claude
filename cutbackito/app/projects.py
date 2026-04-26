"""Project state: filesystem-backed buckets per upload session."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


@dataclass
class ProjectState:
    id: str
    created_at: str
    sources: list[str] = field(default_factory=list)
    sync: list[dict[str, Any]] = field(default_factory=list)
    transcript_path: str | None = None
    transcript_language: str | None = None
    highlights: list[dict[str, Any]] = field(default_factory=list)
    edits: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_dir(project_id: str) -> Path:
    return settings.workspace_dir / project_id


def state_path(project_id: str) -> Path:
    return project_dir(project_id) / "state.json"


def create_project() -> ProjectState:
    pid = uuid.uuid4().hex[:12]
    p = project_dir(pid)
    (p / "sources").mkdir(parents=True, exist_ok=True)
    (p / "exports").mkdir(parents=True, exist_ok=True)
    state = ProjectState(id=pid, created_at=_now())
    save_state(state)
    return state


def save_state(state: ProjectState) -> None:
    state_path(state.id).write_text(json.dumps(state.to_json(), indent=2))


def load_state(project_id: str) -> ProjectState:
    raw = json.loads(state_path(project_id).read_text())
    return ProjectState(**raw)


def list_projects() -> list[ProjectState]:
    out: list[ProjectState] = []
    for p in sorted(settings.workspace_dir.iterdir(), reverse=True):
        if not p.is_dir() or not (p / "state.json").exists():
            continue
        try:
            out.append(load_state(p.name))
        except Exception:
            continue
    return out


def add_source(project_id: str, src_filename: str, content: bytes) -> Path:
    safe = Path(src_filename).name
    dst = project_dir(project_id) / "sources" / safe
    dst.write_bytes(content)
    state = load_state(project_id)
    if str(dst) not in state.sources:
        state.sources.append(str(dst))
        save_state(state)
    return dst


def delete_project(project_id: str) -> None:
    shutil.rmtree(project_dir(project_id), ignore_errors=True)
