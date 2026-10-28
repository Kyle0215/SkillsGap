"""SkillsGap web server (FastAPI).

It does two things:
  1. serves the web page in /web (HTML, CSS, JavaScript);
  2. offers a small JSON API that wraps the existing Python code
     (analysis/matcher.py, utils/text_extraction.py, utils/data_loading.py).

Run locally (PowerShell, with the virtual environment active):
    uvicorn server:app --reload
then open http://127.0.0.1:8000

PRIVACY: nothing is stored. Each request is handled in memory and forgotten.
Uploaded files arrive as base64 inside JSON, so they are read straight into
memory. (Normal form uploads would be written to a temporary file on disk
when they are larger than 1 MB.) Request bodies and syllabus text are never
logged.
"""
from __future__ import annotations

import base64
import binascii
import logging
import time
import traceback
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from analysis.contract import ResultFormatError, check_result
from analysis.matcher import AnalysisError, analyze
from analysis.validation import (
    MAX_REFERENCE_BYTES, MIN_RELIABLE_SKILLS, ReviewFileError, compare_with_reviewer, parse_reference_csv,
)
from utils.data_loading import (
    VALIDATION_METRICS, DataError, check_data, has_pilot_results, load_data_source, load_demand,
    load_skills, load_validation_results,
)
from utils.samples import load_sample, sample_list, sample_name_from_id
from utils.text_extraction import MAX_CHARS, MAX_FILE_BYTES, ExtractionError, extract_text, validate_text

log = logging.getLogger("skillsgap")
WEB_DIR = Path(__file__).resolve().parent / "web"

# A 5 MB file is about 6.7 MB as base64; 8 MB leaves room for the rest of the JSON.
MAX_BODY_BYTES = 8 * 1024 * 1024
METHODS = ("level1", "level2")          # level1 = "Exact", level2 = "Smart" on the web page
GAP_DEMAND_THRESHOLD = 0.20             # "Potential skill gap" = not detected and >= 20% of postings

# Required by the CC BY-SA 4.0 licence of the job-market data (exact text from the data team).
ATTRIBUTION = (
    "Job-market data derived from 'LinkedIn Job Postings (2023 - 2024)' by Arsh Koneru, "
    "Kaggle, CC BY-SA 4.0 (https://www.kaggle.com/datasets/arshkon/linkedin-job-postings). "
    "Filtered and counted by Team ArgonUT."
)
GENERIC_ERROR = "Something went wrong on our side. Please try again."

# The page only loads files from this server (no outside scripts, fonts or frames).
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)

app = FastAPI(title="SkillsGap", docs_url=None, redoc_url=None, openapi_url=None)


# ---------------------------------------------------------------------------
# Errors: always a short JSON message, never a stack trace
# ---------------------------------------------------------------------------

def error_response(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status, headers={"Cache-Control": "no-store"})


@app.exception_handler(RequestValidationError)
async def bad_request(_request: Request, _exc: RequestValidationError):
    return error_response(400, "Some information was missing or not valid. Please check and try again.")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    # Log only the error type and where it happened, never the message or values,
    # because they could contain text from a user's syllabus.
    where = traceback.extract_tb(exc.__traceback__)[-1] if exc.__traceback__ else None
    log.error("Unexpected %s on %s at %s:%s", type(exc).__name__, request.url.path,
              Path(where.filename).name if where else "?", where.lineno if where else "?")
    return error_response(500, GENERIC_ERROR)


@app.middleware("http")
async def limits_and_headers(request: Request, call_next):
    """Reject oversized requests early and add security headers to every response."""
    if request.method == "POST":
        length = request.headers.get("content-length")
        if length is None or not length.isdigit():
            return error_response(411, "The request size is missing.")
        if int(length) > MAX_BODY_BYTES:
            return error_response(413, "The file is too large. The limit is 5 MB.")
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"   # results contain syllabus excerpts
    return response


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    """For the hosting platform's health check."""
    return {"ok": True}


@app.get("/api/meta")
def meta():
    """Everything the start page needs: roles, samples, data source and validation status."""
    try:
        check_data()
        demand = load_demand()
        postings = demand.groupby("role")["total_postings"].first()
        roles = [{"name": role, "postings": int(postings[role])} for role in sorted(postings.index)]
        data_error = None
        skills_total = len(load_skills())
    except DataError as err:
        roles, skills_total, data_error = [], None, f"The job-market data could not be loaded. {err}"

    source = load_data_source()
    pilot = load_validation_results()
    evaluated = has_pilot_results(pilot)
    return {
        "roles": roles,
        "skills_total": skills_total,
        "samples": sample_list(),
        "source": {
            "name": source["name"], "url": source["url"], "licence": source["licence"],
            "collection_method": source["collection_method"], "date_range": source["date_range"],
            "region": source["region"], "postings_used": source["postings_used"],
            "notes": source["notes"],
        },
        "pilot_evaluated": evaluated,
        # Real numbers only when data/validation_results.json has them; otherwise None.
        "pilot": {k: pilot.get(k) for k in [*VALIDATION_METRICS, "notes"]} if evaluated else None,
        "min_reliable_skills": MIN_RELIABLE_SKILLS,
        "max_reference_mb": MAX_REFERENCE_BYTES / (1024 * 1024),
        "gap_threshold": GAP_DEMAND_THRESHOLD,
        "max_file_mb": MAX_FILE_BYTES // (1024 * 1024),
        "max_chars": MAX_CHARS,
        "attribution": ATTRIBUTION,
        "data_error": data_error,
    }


class AnalyzeRequest(BaseModel):
    """What the start page sends. Exactly one of text / sample / file is used, chosen by `source`."""
    source: Literal["upload", "paste", "sample"]
    role: str = Field(min_length=1, max_length=100)
    text: str | None = Field(default=None, max_length=MAX_CHARS * 2)
    sample: str | None = Field(default=None, max_length=100)
    filename: str | None = Field(default=None, max_length=255)
    file_base64: str | None = Field(default=None, max_length=MAX_BODY_BYTES)


def read_syllabus(req: AnalyzeRequest) -> tuple[str, str]:
    """Return (cleaned syllabus text, a label for where it came from). Memory only."""
    if req.source == "paste":
        return validate_text(req.text or ""), "Pasted text"
    if req.source == "sample":
        name = sample_name_from_id(req.sample or "")
        if name is None:
            raise ExtractionError("Please choose one of the sample syllabi.")
        return validate_text(load_sample(name)), name
    if not req.file_base64 or not req.filename:
        raise ExtractionError("Please choose a PDF or DOCX file to upload.")
    try:
        data = base64.b64decode(req.file_base64, validate=True)
    except (binascii.Error, ValueError):
        raise ExtractionError("The file could not be read. Please try uploading it again.") from None
    return extract_text(req.filename, data), Path(req.filename).name


@app.post("/api/analyze")
def analyze_syllabus(req: AnalyzeRequest):
    """Analyse one syllabus for one role with BOTH methods, so the page can switch instantly."""
    start = time.perf_counter()
    try:
        check_data()
        text, source_label = read_syllabus(req)
        results = {}
        for method in METHODS:
            result = analyze(text, req.role, method)
            check_result(result)
            results[method] = result
    except (ExtractionError, AnalysisError) as err:
        return error_response(400, str(err))
    except DataError as err:
        return error_response(503, f"The job-market data could not be loaded. {err}")
    except ResultFormatError as err:
        return error_response(500, str(err))
    return {
        "role": req.role,
        "source_label": source_label,
        "elapsed_seconds": round(time.perf_counter() - start, 3),
        "results": results,
    }


class ValidateRequest(BaseModel):
    """The lecturer's reference CSV (base64, so Excel's encodings survive) and the
    current analysis results that the page already holds (the server keeps none)."""
    reference_base64: str = Field(min_length=1, max_length=MAX_REFERENCE_BYTES * 2)
    results: dict[str, dict]


MAX_SKILLS_PER_RESULT = 500


@app.post("/api/validate")
def validate_against_reviewer(req: ValidateRequest):
    """Precision / recall / F1 for both methods, with 'brief' counted as covered and not."""
    try:
        results = {m: req.results[m] for m in METHODS if m in req.results}
        if not results:
            raise ResultFormatError("Please analyse a syllabus first.")
        for result in results.values():
            check_result(result)
            if len(result["skills"]) > MAX_SKILLS_PER_RESULT:
                raise ResultFormatError("These results are too large to check.")
        try:
            data = base64.b64decode(req.reference_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ReviewFileError("The file could not be read. Please try uploading it again.") from None
        reference, n_blank = parse_reference_csv(data)
    except ReviewFileError as err:
        return error_response(400, str(err))
    except ResultFormatError:
        return error_response(400, "Your results could not be checked. Please run the analysis again.")

    comparisons = {
        key: {m: compare_with_reviewer(r, reference, brief_counts_as_covered=brief) for m, r in results.items()}
        for key, brief in (("brief_on", True), ("brief_off", False))
    }
    return {"rows": len(reference), "blank": n_blank, "comparisons": comparisons}


# ---------------------------------------------------------------------------
# The web page (must come last, so it doesn't hide the /api routes)
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
