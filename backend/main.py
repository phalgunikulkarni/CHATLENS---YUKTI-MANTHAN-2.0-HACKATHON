import json
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import schemas
from schemas import (
    MemoryResult,
    ExplanationSignal,
    TurnResponse,
    TurnSearchRequest,
    RefineRequestBody,
    SummarizeRequestBody,
    SummaryResponseBody,
    RoadmapRequestBody,
    RoadmapResponseBody,
    ImageStatus,
)
from retrieval import hybrid_search
import models
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ChatLens API", description="AI-powered personal visual memory search engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _to_memory_result(record) -> MemoryResult:
    """
    Map a backend Image DB row (or ImageRecord from hybrid_search) to a
    MemoryResult in the frontend-canonical shape.

    NOTE: The retrieval engine is not integrated yet, so we intentionally do
    NOT fabricate retrieval signals. `matchScore` and `explanation` are left as
    None. `thumbnailUrl` is a passthrough of the stored image_reference and may
    not be a real URL — this is an accepted known limitation.
    """
    # metadata may be a parsed dict (ImageRecord) or None; coerce values to str.
    raw_meta = getattr(record, "metadata", None)
    if raw_meta:
        metadata = {str(k): str(v) for k, v in raw_meta.items()}
    else:
        metadata = None

    timestamp = getattr(record, "timestamp", None)
    captured_at = timestamp.isoformat() if timestamp else None

    return MemoryResult(
        id=record.image_id,
        thumbnailUrl=record.image_reference,  # passthrough; do NOT fabricate
        fullUrl=None,
        ocrSnippet=getattr(record, "ocr_text", None),
        matchScore=None,  # retrieval engine not integrated; do NOT invent a score
        sourceTag=getattr(record, "source", None),
        capturedAt=captured_at,
        metadata=metadata,
        explanation=None,  # no real retrieval signals yet; do NOT fabricate
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/search", response_model=TurnResponse)
def search(request: TurnSearchRequest, db: Session = Depends(get_db)):
    session_id = request.sessionId or f"session_{uuid.uuid4().hex[:8]}"
    results = [_to_memory_result(r) for r in hybrid_search(db, request.query)]
    return TurnResponse(
        sessionId=session_id,
        intent="search",
        agentMessage=f"Found {len(results)} memories.",
        clues=[],
        results=results,
    )


@app.post("/api/refine", response_model=TurnResponse)
def refine(request: RefineRequestBody, db: Session = Depends(get_db)):
    results = [_to_memory_result(r) for r in hybrid_search(db, request.message)]
    return TurnResponse(
        sessionId=request.sessionId,
        intent="refinement",
        agentMessage=f"Refined search. {len(results)} memories.",
        clues=request.activeClues,  # echo back active clues unchanged
        results=results,
    )


@app.get("/api/results/{result_id}/explanation", response_model=List[ExplanationSignal])
def get_explanation(result_id: str):
    # Real retrieval signals are not available yet. Return an empty list; the
    # frontend renders an "explanation not available" state for an empty array.
    # Do NOT fabricate signals.
    return []


@app.post("/api/actions/summarize", response_model=SummaryResponseBody)
def summarize_images(request: SummarizeRequestBody):
    return SummaryResponseBody(
        sessionId=request.sessionId,
        summary=(
            "Summarization requires the retrieval/LLM service, which is not "
            f"connected yet. {len(request.imageIds)} memories were selected."
        ),
        usedImageIds=request.imageIds,
    )


@app.post("/api/actions/roadmap", response_model=RoadmapResponseBody)
def generate_roadmap(request: RoadmapRequestBody):
    # Real generation is not connected; return an empty steps list. The
    # frontend renders only supplied steps. Do NOT fabricate roadmap content.
    return RoadmapResponseBody(sessionId=request.sessionId, steps=[])


@app.post("/api/images", response_model=ImageStatus)
def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Do NOT run OCR/CLIP and do NOT persist the binary. Create a minimal DB row
    # so the status is queryable.
    image_id = f"img_{uuid.uuid4().hex[:8]}"
    db_image = models.Image(
        image_id=image_id,
        image_reference=file.filename,
        source="upload",
        timestamp=datetime.utcnow(),
        ocr_text=None,
        metadata_json=None,
    )
    db.add(db_image)
    db.commit()
    return ImageStatus(imageId=image_id, status="processing")


@app.get("/api/images/{image_id}/status", response_model=ImageStatus)
def get_image_status(image_id: str, db: Session = Depends(get_db)):
    r = db.query(models.Image).filter(models.Image.image_id == image_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Image not found")
    return ImageStatus(imageId=image_id, status="ready")
