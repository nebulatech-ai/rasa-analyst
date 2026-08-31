from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

import settings
from engine.client import OllamaError, analyze_content, list_models, rasa_model_present
from engine.extract import docx_to_text, fetch_url, html_to_text
from engine.schema import AnalysisResult, finalize
from engine.version import APP_VERSION, DEFAULT_MODEL, ENGINE, MODEL_FAMILY

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
MAX_UPLOAD = 2_000_000
TEXT_EXT = (".txt", ".md", ".csv", ".html", ".htm")
DOCX_EXT = (".docx",)

app = FastAPI(
    title="RASA-Analyst",
    description="Local GEO workbench. Nebula Personalization Tech Solutions Pvt. Ltd.",
    version=APP_VERSION,
    docs_url="/docs" if settings.DOCS_ON else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.DOCS_ON else None,
)
app.add_middleware(GZipMiddleware, minimum_size=512)
if "*" not in settings.ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.middleware("http")
async def production_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    path = request.url.path
    if path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-store"
    elif path.startswith("/assets/"):
        response.headers.setdefault("Cache-Control", "public, max-age=3600")
    return response


class AnalyzeBody(BaseModel):
    content: str = Field(min_length=20, max_length=20000)


class FetchBody(BaseModel):
    url: str


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health() -> dict:
    """Liveness: the workbench process is up."""
    return {"ok": True, "engine": ENGINE, "version": APP_VERSION, "env": settings.ENV}


@app.get("/api/ready")
async def ready():
    """Readiness: Ollama is up and the RASA-Analyst model is installed."""
    payload = {
        "ok": False,
        "ollama": False,
        "preferred": DEFAULT_MODEL,
        "preferred_present": False,
        "engine": ENGINE,
        "version": APP_VERSION,
        "model_family": MODEL_FAMILY,
        "env": settings.ENV,
    }
    try:
        models = await list_models()
        present = rasa_model_present(models)
        payload.update({"ok": present, "ollama": True, "preferred_present": present})
        if not present:
            return JSONResponse(status_code=503, content=payload)
        return payload
    except OllamaError as e:
        payload["error"] = str(e)
        return JSONResponse(status_code=503, content=payload)


async def _run(content: str) -> AnalysisResult:
    text = content.strip()
    try:
        judgement, seed = await analyze_content(text, model=DEFAULT_MODEL)
        return finalize(judgement, model=DEFAULT_MODEL, seed=seed, content=text)
    except OllamaError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/analyze")
async def analyze(body: AnalyzeBody) -> AnalysisResult:
    return await _run(body.content)


@app.post("/api/analyze-url")
async def analyze_url(body: FetchBody) -> AnalysisResult:
    try:
        text = await fetch_url(body.url.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch that URL: {e}") from e
    return await _run(text)


@app.post("/api/analyze-file")
async def analyze_file(file: UploadFile = File(...)) -> AnalysisResult:
    name = (file.filename or "upload").lower()
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File is larger than 2 MB. Paste a section instead.")
    if name.endswith(DOCX_EXT):
        try:
            text = docx_to_text(raw)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return await _run(text)
    if not name.endswith(TEXT_EXT):
        raise HTTPException(
            status_code=400,
            detail="Upload a .txt, .md, .csv, .html, or .docx file.",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    if name.endswith((".html", ".htm")):
        text = html_to_text(text)
    if len(text.strip()) < 20:
        raise HTTPException(status_code=400, detail="File did not contain enough text.")
    return await _run(text)
