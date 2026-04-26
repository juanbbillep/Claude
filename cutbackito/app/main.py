"""FastAPI app for Cutbackito."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .chat_editor import EditPlan, plan_edit
from .config import settings
from .exporter import export_plan
from .ffmpeg_utils import probe
from .highlights import detect_highlights
from .multicam_sync import SyncedSource, common_window, sync_sources
from . import projects
from .transcription import Segment, Transcript, transcribe


BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Cutbackito", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"projects": projects.list_projects()},
    )


@app.post("/projects")
def create_project():
    state = projects.create_project()
    return RedirectResponse(url=f"/projects/{state.id}", status_code=303)


@app.get("/projects/{project_id}", response_class=HTMLResponse)
def show_project(project_id: str, request: Request):
    try:
        state = projects.load_state(project_id)
    except FileNotFoundError:
        raise HTTPException(404, "project not found")
    return templates.TemplateResponse(
        request,
        "project.html",
        {
            "state": state,
            "anthropic_configured": bool(settings.anthropic_api_key),
            "exports": _list_exports(project_id),
        },
    )


@app.post("/projects/{project_id}/sources")
async def upload_source(project_id: str, files: list[UploadFile] = File(...)):
    state = projects.load_state(project_id)
    for f in files:
        max_bytes = settings.max_upload_mb * 1024 * 1024
        content = await f.read()
        if len(content) > max_bytes:
            raise HTTPException(413, f"{f.filename} exceeds {settings.max_upload_mb} MB")
        projects.add_source(project_id, f.filename or "upload.mp4", content)
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@app.post("/projects/{project_id}/sync")
def run_sync(project_id: str):
    state = projects.load_state(project_id)
    if len(state.sources) < 1:
        raise HTTPException(400, "Upload at least one source first.")
    sources = [Path(s) for s in state.sources]
    workspace = projects.project_dir(project_id) / "tmp"
    workspace.mkdir(exist_ok=True)
    synced = sync_sources(sources, workspace)
    state.sync = [
        {
            "name": s.name,
            "path": str(s.path),
            "duration": s.duration,
            "offset_seconds": s.offset_seconds,
            "confidence": s.confidence,
        }
        for s in synced
    ]
    projects.save_state(state)
    start, end = common_window(synced)
    return {
        "sync": state.sync,
        "common_window": {"start": start, "end": end, "length": max(0.0, end - start)},
    }


@app.post("/projects/{project_id}/transcribe")
def run_transcribe(project_id: str):
    state = projects.load_state(project_id)
    if not state.sync:
        raise HTTPException(400, "Sync the cameras first.")
    reference = max(state.sync, key=lambda s: s["confidence"])
    media = Path(reference["path"])
    info = probe(media)
    if not info.has_audio:
        raise HTTPException(400, "Reference camera has no audio track.")

    transcript = transcribe(media)
    out = projects.project_dir(project_id) / "transcript.json"
    out.write_text(json.dumps(transcript.to_dict(), indent=2))

    state.transcript_path = str(out)
    state.transcript_language = transcript.language
    projects.save_state(state)
    return transcript.to_dict()


@app.post("/projects/{project_id}/highlights")
def run_highlights(project_id: str, top_k: int = Form(5), seconds: float = Form(30.0)):
    state = projects.load_state(project_id)
    transcript = _load_transcript(state)
    reference = max(state.sync, key=lambda s: s["confidence"])
    workspace = projects.project_dir(project_id) / "tmp"
    workspace.mkdir(exist_ok=True)
    hits = detect_highlights(
        transcript, Path(reference["path"]), workspace, top_k=top_k, target_seconds=seconds
    )
    state.highlights = [asdict(h) for h in hits]
    projects.save_state(state)
    return state.highlights


@app.post("/projects/{project_id}/chat")
def run_chat(project_id: str, instruction: str = Form(...)):
    state = projects.load_state(project_id)
    transcript = _load_transcript(state)
    if not state.sync:
        raise HTTPException(400, "Sync the cameras first.")
    plan = plan_edit(instruction, transcript, state.sync)

    cameras = _load_synced_sources(state)
    out_dir = projects.project_dir(project_id) / "exports"
    exports = export_plan(plan, cameras, transcript, out_dir)

    state.edits.append(
        {
            "instruction": instruction,
            "summary": plan.summary,
            "clips": [
                {
                    "title": e.clip.title,
                    "format": e.clip.format,
                    "camera": e.clip.camera,
                    "start": e.clip.start,
                    "end": e.clip.end,
                    "path": e.path.name,
                }
                for e in exports
            ],
        }
    )
    projects.save_state(state)
    return {"summary": plan.summary, "clips": [e.path.name for e in exports]}


@app.get("/projects/{project_id}/exports/{filename}")
def download_export(project_id: str, filename: str):
    safe = Path(filename).name
    path = projects.project_dir(project_id) / "exports" / safe
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="video/mp4", filename=safe)


@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    projects.delete_project(project_id)
    return JSONResponse({"ok": True})


@app.get("/healthz")
def health():
    return {
        "ok": True,
        "anthropic_configured": bool(settings.anthropic_api_key),
        "whisper_model": settings.whisper_model,
    }


def _list_exports(project_id: str) -> list[str]:
    out_dir = projects.project_dir(project_id) / "exports"
    if not out_dir.exists():
        return []
    return sorted(p.name for p in out_dir.glob("*.mp4"))


def _load_transcript(state: projects.ProjectState) -> Transcript:
    if not state.transcript_path:
        raise HTTPException(400, "Transcribe first.")
    raw = json.loads(Path(state.transcript_path).read_text())
    return Transcript(
        language=raw["language"],
        segments=[Segment(**s) for s in raw["segments"]],
    )


def _load_synced_sources(state: projects.ProjectState) -> list[SyncedSource]:
    return [
        SyncedSource(
            name=s["name"],
            path=Path(s["path"]),
            duration=s["duration"],
            offset_seconds=s["offset_seconds"],
            confidence=s["confidence"],
        )
        for s in state.sync
    ]
