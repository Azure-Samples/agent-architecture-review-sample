"""
Architecture Review Agent — FastAPI Backend
=============================================
Exposes the smart_parse → analyze_risks → generate_excalidraw_elements →
export_png → build_review_report pipeline as REST endpoints.
Serves the React frontend static files in production.
"""

import asyncio
import io
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tools import (
    smart_parse,
    infer_architecture_llm,
    analyze_risks,
    generate_excalidraw_elements,
    build_component_map,
    save_excalidraw_file,
    export_png,
    build_review_report,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

logger = logging.getLogger("arch-review.api")

# Maximum input size (characters) to prevent abuse
MAX_INPUT_SIZE = 500_000  # ~500 KB of text

app = FastAPI(
    title="Architecture Review Agent API",
    description="AI Architecture Reviewer & Diagram Generator",
    version="1.0.0",
)

# CORS: restrict to localhost during development.
# In production, set ALLOWED_ORIGINS env var to your domain(s), comma-separated.
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory for generated files
OUTPUT_DIR = Path("./output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ReviewRequest(BaseModel):
    content: str
    force_infer: bool = False


class InferRequest(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_run_id(run_id: str) -> str:
    """Sanitise run_id to prevent path traversal — must be a short hex string."""
    if not re.fullmatch(r"[0-9a-fA-F]{1,16}", run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id format")
    return run_id


def _run_pipeline(parsed: dict) -> dict:
    """Run risk analysis → diagram → component map → report."""
    # Risk analysis
    if parsed.get("llm_risks"):
        llm_risks = parsed["llm_risks"]
        risks: dict = {"critical": [], "high": [], "medium": [], "low": []}
        for r in llm_risks:
            risks[r.get("severity", "medium")].append(r)
        risks["summary"] = {
            "total": len(llm_risks),
            "critical": len(risks["critical"]),
            "high": len(risks["high"]),
            "medium": len(risks["medium"]),
            "low": len(risks["low"]),
        }
    else:
        risks = analyze_risks(parsed["components"], parsed["connections"])

    # Component map
    comp_map = build_component_map(parsed["components"], parsed["connections"])

    # Diagram generation
    file_elems = generate_excalidraw_elements(
        parsed["components"], parsed["connections"]
    )

    # Save files with unique ID to avoid collisions
    run_id = uuid.uuid4().hex[:8]
    excalidraw_path = str(OUTPUT_DIR / f"architecture_{run_id}.excalidraw")
    png_path = str(OUTPUT_DIR / f"architecture_{run_id}.png")

    saved = save_excalidraw_file(file_elems["elements_json"], excalidraw_path)
    png_saved = export_png(
        parsed["components"], parsed["connections"], png_path
    )

    # Read excalidraw file
    with open(saved, "r", encoding="utf-8") as f:
        excalidraw_file = json.load(f)

    diagram_info = {
        "element_count": file_elems["element_count"],
        "local_file": saved,
        "png_file": png_saved,
        "excalidraw_file": excalidraw_file,
        "run_id": run_id,
    }

    report = build_review_report(parsed, risks, comp_map, diagram_info)
    return report


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Architecture Review Agent"}


@app.post("/api/review")
async def review_architecture(req: ReviewRequest):
    """Full architecture review pipeline."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    if len(req.content) > MAX_INPUT_SIZE:
        raise HTTPException(status_code=413, detail=f"Input too large (max {MAX_INPUT_SIZE:,} characters)")

    try:
        if req.force_infer:
            parsed = await infer_architecture_llm(req.content)
            if parsed.get("error"):
                # Fallback to rule-based
                from tools import parse_architecture
                parsed = parse_architecture(req.content)
        else:
            parsed = await smart_parse(req.content)

        if not parsed.get("components"):
            raise HTTPException(
                status_code=422,
                detail="No components could be extracted from the input",
            )

        report = _run_pipeline(parsed)
        return JSONResponse(content=report)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Review pipeline failed")
        raise HTTPException(status_code=500, detail="Internal server error — check server logs for details")


@app.post("/api/review/upload")
async def review_upload(file: UploadFile = File(...), force_infer: bool = False):
    """Upload a file for architecture review."""
    content = (await file.read()).decode("utf-8", errors="replace")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > MAX_INPUT_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_INPUT_SIZE:,} characters)")

    try:
        if force_infer:
            parsed = await infer_architecture_llm(content)
            if parsed.get("error"):
                from tools import parse_architecture
                parsed = parse_architecture(content)
        else:
            parsed = await smart_parse(content)

        if not parsed.get("components"):
            raise HTTPException(
                status_code=422,
                detail="No components could be extracted from the uploaded file",
            )

        report = _run_pipeline(parsed)
        return JSONResponse(content=report)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Upload pipeline failed")
        raise HTTPException(status_code=500, detail="Internal server error — check server logs for details")


@app.post("/api/infer")
async def infer_architecture(req: InferRequest):
    """LLM inference only — extract architecture from unstructured text."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    if len(req.content) > MAX_INPUT_SIZE:
        raise HTTPException(status_code=413, detail=f"Input too large (max {MAX_INPUT_SIZE:,} characters)")

    try:
        result = await infer_architecture_llm(req.content)
        return JSONResponse(content=result)
    except Exception as exc:
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail="Internal server error — check server logs for details")


@app.get("/api/download/png/{run_id}")
async def download_png(run_id: str):
    """Download generated PNG diagram."""
    run_id = _validate_run_id(run_id)
    path = OUTPUT_DIR / f"architecture_{run_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="PNG not found")
    return FileResponse(
        str(path), media_type="image/png", filename="architecture.png"
    )


@app.get("/api/download/excalidraw/{run_id}")
async def download_excalidraw(run_id: str):
    """Download generated Excalidraw file."""
    run_id = _validate_run_id(run_id)
    path = OUTPUT_DIR / f"architecture_{run_id}.excalidraw"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Excalidraw file not found")
    return FileResponse(
        str(path),
        media_type="application/json",
        filename="architecture.excalidraw",
    )


# ---------------------------------------------------------------------------
# Serve React frontend in production
# ---------------------------------------------------------------------------

_FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
