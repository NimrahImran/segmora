"""Segmora API: customer segmentation, explanations, personas and contact."""
from __future__ import annotations

import io
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .config import get_settings
from .schemas import ContactRequest, CustomerInput, PersonaRequest, ReportRequest
from .services import analysis as analysis_svc
from .services import contact as contact_svc
from .services import ingest, persona, report
from .services.features import BASE_FEATURES
from .services.segmentation import SEGMENT_META, SegmentModel, fit_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("segmora")
settings = get_settings()
MIN_OWN_CUSTOMERS = 40
hits: dict[str, deque] = defaultdict(deque)

app = FastAPI(title="Segmora API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None,
              description="Sorts customers into four behaviour segments, explains every decision and writes "
                          "a persona for each group. The API keeps no customer data between requests.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
                   allow_origin_regex=settings.allowed_origin_regex or None, allow_methods=["GET", "POST"],
                   allow_headers=["*"], expose_headers=["X-Request-ID"])


@lru_cache
def get_model() -> SegmentModel:
    return SegmentModel.load(settings.model_path)


@lru_cache
def get_sample() -> pd.DataFrame:
    return pd.read_csv(settings.data_path, dtype={"customer_id": str})


@lru_cache
def get_baseline() -> dict:
    return analysis_svc.build(get_model(), get_sample(),
                              {"kind": "baseline", "label": "UCI Online Retail, a real UK store, 2010 to 2011"}, currency="£")


@app.middleware("http")
async def guard(request: Request, call_next):
    request_id = uuid.uuid4().hex[:10]
    if request.method == "POST":
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")).split(",")[0]
        live = request.url.path == "/api/predict"  # sliders call this on every change
        limit = settings.rate_limit_per_minute * (8 if live else 1)
        window, now = hits[f"{ip}:{live}"], time.monotonic()
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            return JSONResponse({"detail": "Too many requests. Wait a minute and try again."}, status_code=429)
        window.append(now)
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info("%s %s %s %.0fms id=%s", request.method, request.url.path, response.status_code,
             (time.perf_counter() - started) * 1000, request_id)
    return response


@app.get("/api/health", tags=["system"])
def health():
    get_model()
    return {"status": "ok", "model_loaded": True, "persona_ai": bool(settings.gemini_api_key),
            "contact_form": bool(settings.gmail_user and settings.gmail_app_password)}


@app.get("/api/segments", tags=["segments"])
def segments():
    return SEGMENT_META


@app.get("/api/analysis", tags=["analysis"], summary="The demo store: segments, 3D points, priority list")
def read_baseline():
    return get_baseline()


@app.post("/api/predict", tags=["segments"], summary="Segment one customer")
def predict(customer: CustomerInput):
    model = get_model()
    row = pd.DataFrame([customer.model_dump()])[BASE_FEATURES]
    result = model.predict(row).iloc[0]
    span = get_baseline()["span"]
    coords = (model.project(row)[0] / span).clip(-1.2, 1.2)
    meta = SEGMENT_META[result["segment"]]
    return {"segment": result["segment"], "name": meta["name"], "tagline": meta["tagline"],
            "strength": float(result["strength"]), "reasons": model.explain(row.iloc[0], result["segment"]),
            "position": {"x": round(float(coords[0]), 3), "y": round(float(coords[1]), 3), "z": round(float(coords[2]), 3)}}


@app.post("/api/analyze", tags=["analysis"], summary="Segment a CSV or Excel file")
async def analyze(file: UploadFile = File(...), mode: str = Form("standard"), mapping: str = Form("{}")):
    if mode not in ("standard", "own"):
        raise HTTPException(422, "Mode must be 'standard' or 'own'.")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"This file is larger than {settings.max_upload_mb} MB.")
    try:
        parsed_mapping = json.loads(mapping or "{}")
        table = ingest.read_table(content, file.filename or "", settings.max_rows)
        customers, info = ingest.to_customers(table, parsed_mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "The column matching could not be read.") from exc
    except ingest.IngestError as exc:
        return JSONResponse({"detail": str(exc), "columns": exc.columns, "missing": exc.missing}, status_code=422)
    if len(customers) > settings.max_customers:
        raise HTTPException(422, f"This file has more than {settings.max_customers:,} customers. Split it and upload again.")
    model, note = get_model(), None
    if mode == "own":
        if len(customers) >= MIN_OWN_CUSTOMERS:
            model = fit_model(customers)
        else:
            mode, note = "standard", f"Fewer than {MIN_OWN_CUSTOMERS} customers, so the ready-made model was used."
    return analysis_svc.build(model, customers, {"kind": "upload", "label": file.filename, "mode": mode, "note": note, **info})


@app.post("/api/personas", tags=["personas"], summary="Write the persona for a segment from its averages")
def write_persona(body: PersonaRequest):
    if body.segment.customers == 0:
        raise HTTPException(422, "This data has no customers in that segment.")
    return persona.make({**body.segment.model_dump(), **SEGMENT_META[body.segment.key]}, body.currency)


@app.post("/api/report.pdf", tags=["reports"], summary="Build the PDF summary")
def download_pdf(body: ReportRequest):
    return Response(report.pdf(body.model_dump()), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="segmora_report.pdf"'})


@app.get("/api/sample.csv", tags=["reports"], summary="A small file to try the upload with")
def sample_csv():
    buffer = io.StringIO()
    get_sample().sample(300, random_state=3).to_csv(buffer, index=False)
    return PlainTextResponse(buffer.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="segmora_sample.csv"'})


@app.post("/api/contact", tags=["contact"], summary="Send a message to the site owner's Gmail")
def contact(body: ContactRequest):
    try:
        contact_svc.send(body)
    except contact_svc.ContactError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return {"ok": True}


@app.get("/api/model", tags=["system"], summary="Model card")
def model_card():
    return {**get_model().meta, "limits": [
        "Trained on one UK online store from 2010 to 2011, mostly wholesale-style buyers.",
        "Silhouette of about 0.25 means groups overlap. This is normal for customer behaviour.",
        "Three groups score slightly higher, but four were chosen because they map to clearer business actions.",
        "Segment names come from measured behaviour. Lifestyle text in personas is interpretation, not measurement.",
        "The source data has no discount field, so Deal Hunter is inferred from low order value and long inactivity.",
    ], "persona_ai": bool(settings.gemini_api_key)}
