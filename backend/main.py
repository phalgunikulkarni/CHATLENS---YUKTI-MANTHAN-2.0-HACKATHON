import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import backend.models as models
from backend.database import engine, SessionLocal
from backend.schemas import (
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
    AccessGrantResult,
    AccessStatus,
    CreateChat,
    ConversationSummary,
    ConversationDetail,
)
import backend.ingestion as ingestion
import backend.ml_retrieval as ml_retrieval
import backend.access_service as access_service
import backend.chat_repo as chat_repo
import backend.db_init as db_init
from backend.account import resolve_account

# Create tables in SQLite (creates the new search_result_refs table and, for a
# fresh DB, the new account_id/title columns).
models.Base.metadata.create_all(bind=engine)

# Additively ensure account_id/title columns exist on any PRE-EXISTING tables
# that create_all() will not ALTER. Strictly additive; aborts without touching
# data on failure. (Full migration module is task 8.1, deferred to Phase H.)
try:
    db_init.ensure_account_columns(engine)
except Exception as e:  # noqa: BLE001 - surface but do not crash import in dev
    print(f"[db_init] additive column-ensure failed: {e}")

app = FastAPI(
    title="ChatLens API",
    description="AI-powered personal visual memory search engine",
)

# Allowed browser origins for CORS. Defaults to local dev; in hosting set
# CHATLENS_ALLOWED_ORIGINS to a comma-separated list of deployed frontend
# origins (e.g. "https://chatlens-frontend.onrender.com"). Local dev is
# unchanged when the env var is unset.
_DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
_env_origins = os.environ.get("CHATLENS_ALLOWED_ORIGINS", "").strip()
_allowed_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _DEFAULT_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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


def _status_to_frontend(processing_status: str) -> str:
    """Map DB processing_status to the frontend ProcessingStatus vocabulary."""
    mapping = {
        "pending": "processing",
        "processing": "processing",
        "ready": "ready",
        "failed": "failed",
    }
    return mapping.get(processing_status, "processing")


def _build_memory_result(raw: dict) -> MemoryResult:
    """
    Build a MemoryResult from an adapter search dict. Explanation signals (if
    present) are converted into ExplanationSignal objects; they are grounded in
    real retrieval evidence produced by the ml/ retriever.
    """
    data = ml_retrieval.to_memory_result_dict(raw)
    expl = data.pop("explanation", None)
    explanation = [ExplanationSignal(**s) for s in expl] if expl else None
    return MemoryResult(explanation=explanation, **data)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/search", response_model=TurnResponse)
def search(
    request: TurnSearchRequest,
    account: str = Depends(resolve_account),
    db: Session = Depends(get_db),
):
    # Retrieval is UNCHANGED (no account threading into retrieval — that is a
    # later phase). Persistence wraps around the existing call: run the search,
    # then persist the query + returned result refs under the resolved account.
    #
    # Session resolution for persistence:
    #  - a provided sessionId owned by the account -> append to it
    #  - a provided sessionId owned by another account -> 403 (via _owned_or_raise,
    #    surfaced before any persistence)
    #  - no sessionId -> create a backend-authoritative conversation and return its id
    if request.sessionId:
        # Verify ownership up front; cross-account -> 403, missing -> 404.
        chat_repo._owned_or_raise(db, account, request.sessionId)
        session_id = request.sessionId
    else:
        session_id = chat_repo.create_conversation(db, account)

    raw = ml_retrieval.search_memories(request.query, top_k=5)
    results = [_build_memory_result(r) for r in raw]

    chat_repo.append_search_turn(db, account, session_id, request.query, raw)

    return TurnResponse(
        sessionId=session_id,
        intent="search",
        agentMessage=f"Found {len(results)} memories.",
        clues=[],
        results=results,
    )


@app.post("/api/refine", response_model=TurnResponse)
def refine(
    request: RefineRequestBody,
    account: str = Depends(resolve_account),
    db: Session = Depends(get_db),
):
    # Retrieval UNCHANGED. Refinement is persisted onto the SAME owned
    # conversation; cross-account/nonexistent sessionId -> 403/404 with nothing
    # persisted (surfaced before persistence).
    chat_repo._owned_or_raise(db, account, request.sessionId)

    raw = ml_retrieval.search_memories(request.message, top_k=5)
    results = [_build_memory_result(r) for r in raw]

    clue_dicts = [c.model_dump() for c in request.activeClues]
    chat_repo.append_refine_turn(
        db, account, request.sessionId, request.message, clue_dicts, raw
    )

    return TurnResponse(
        sessionId=request.sessionId,
        intent="refinement",
        agentMessage=f"Refined search. {len(results)} memories.",
        clues=request.activeClues,  # echo back active clues unchanged
        results=results,
    )


# ---------------------------------------------------------------------------
# Account-scoped chat CRUD (Phase B). All via Depends(resolve_account); each
# returns explicit 403/404 for cross-account/missing sessions (never 200-empty).
# ---------------------------------------------------------------------------

@app.post("/api/chats", response_model=ConversationSummary)
def create_chat(
    request: CreateChat = CreateChat(),
    account: str = Depends(resolve_account),
    db: Session = Depends(get_db),
):
    session_id = chat_repo.create_conversation(db, account, title=request.title)
    detail = chat_repo.get_conversation(db, account, session_id)
    return ConversationSummary(
        sessionId=detail["sessionId"],
        title=detail["title"],
        createdAt=detail["createdAt"],
        updatedAt=detail["updatedAt"],
    )


@app.get("/api/chats", response_model=List[ConversationSummary])
def list_chats(account: str = Depends(resolve_account), db: Session = Depends(get_db)):
    return [ConversationSummary(**s) for s in chat_repo.list_conversations(db, account)]


@app.get("/api/chats/{session_id}", response_model=ConversationDetail)
def get_chat(
    session_id: str,
    account: str = Depends(resolve_account),
    db: Session = Depends(get_db),
):
    return ConversationDetail(**chat_repo.get_conversation(db, account, session_id))


@app.patch("/api/chats/{session_id}", response_model=ConversationSummary)
def rename_chat(
    session_id: str,
    request: CreateChat,
    account: str = Depends(resolve_account),
    db: Session = Depends(get_db),
):
    return ConversationSummary(**chat_repo.rename_conversation(db, account, session_id, request.title))


@app.delete("/api/chats/{session_id}")
def delete_chat(
    session_id: str,
    account: str = Depends(resolve_account),
    db: Session = Depends(get_db),
):
    chat_repo.delete_conversation(db, account, session_id)
    return {"deleted": session_id}


@app.get("/api/results/{result_id}/explanation", response_model=List[ExplanationSignal])
def get_explanation(result_id: str):
    # Explanations are grounded in real retrieval evidence. Without a query
    # context we cannot produce grounded signals for a stored image id, so we
    # return an empty list (frontend shows an "explanation not available" state).
    # Do NOT fabricate signals.
    signals = ml_retrieval.explanation_signals_for(result_id)  # returns [] (grounded-only)
    return [ExplanationSignal(**s) for s in signals]


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
    # Real generation is not connected; return an empty steps list. Do NOT
    # fabricate roadmap content.
    return RoadmapResponseBody(sessionId=request.sessionId, steps=[])


@app.post("/api/images", response_model=ImageStatus)
def upload_image(
    file: UploadFile = File(...),
    source: str = Form(None),
    db: Session = Depends(get_db),
):
    # Store the uploaded file + create the Image row (processing_status="pending").
    # Canonical retrieval/indexing is handled by the ml/ Chroma pipeline, not
    # the FAISS processing pipeline, so we do NOT trigger the FAISS background task.
    db_image = ingestion.save_uploaded_image(db, file, source)
    return ImageStatus(
        imageId=db_image.id,
        status=_status_to_frontend(db_image.processing_status),
    )


@app.get("/api/images/{image_id}/status", response_model=ImageStatus)
def get_image_status(
    image_id: str,
    db: Session = Depends(get_db),
    account: str = Depends(resolve_account),
):
    r = db.query(models.Image).filter(models.Image.id == image_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Image not found")
    return ImageStatus(
        imageId=image_id,
        status=_status_to_frontend(r.processing_status),
    )


@app.get("/api/images/{image_id}/file")
def get_image_file(image_id: str, account: str = Depends(resolve_account)):
    # Read-only serving of an already-indexed local image, resolved from the
    # canonical ML/Chroma record by its path-hash id. Never accepts a client
    # path; resolve_image_path validates existence, image type, and that the
    # file is within its authorized indexed location.
    path = ml_retrieval.resolve_image_path(image_id)
    if not path:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


@app.get("/api/library", response_model=List[MemoryResult])
def list_library(account: str = Depends(resolve_account)):
    # Strictly read-only over the existing Chroma index. Does NOT scan,
    # ingest, embed, or index. Returns [] honestly when empty/unavailable.
    raw = ml_retrieval.list_memories()
    return [_build_memory_result(r) for r in raw]


@app.post("/api/access/grant", response_model=AccessGrantResult)
def access_grant(account: str = Depends(resolve_account)):
    # Opens the native folder picker, validates + persists authorized roots,
    # and kicks off background initial indexing. "authorized" here means the
    # authorization was accepted / indexing started; the frontend polls
    # /api/access/status for the "ready" state.
    r = access_service.grant_access(account)
    return AccessGrantResult(
        authorized=bool(r.get("authorized")),
        roots=r.get("roots", []),
        message=r.get("message", ""),
    )


@app.get("/api/access/status", response_model=AccessStatus)
def access_status(account: str = Depends(resolve_account)):
    s = access_service.get_status(account)
    return AccessStatus(
        authorized=bool(s.get("authorized")),
        indexing=s.get("indexing", "idle"),
        roots=s.get("roots", []),
        indexedCount=int(s.get("indexedCount", 0)),
        error=s.get("error"),
    )


@app.on_event("startup")
def _on_startup():
    # Restore persisted authorization and restart the watcher (no full re-index).
    try:
        access_service.restore_on_startup()
    except Exception as e:  # noqa: BLE001 - startup must never crash the app
        print(f"[access] restore failed: {e}")


@app.on_event("shutdown")
def _on_shutdown():
    try:
        access_service.shutdown()
    except Exception as e:  # noqa: BLE001
        print(f"[access] shutdown failed: {e}")
