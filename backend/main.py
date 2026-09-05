import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import models
from database import engine, SessionLocal
from schemas import (
    MemoryResult,
    ExplanationSignal,
    TurnResponse,
    TurnSearchRequest,
    RefineRequestBody,
    SummarizeRequestBody,
    SummaryResponseBody,
    RelatedMemoriesRequestBody,
    AnalyzeBillRequestBody,
    ResearchRequestBody,
    RoadmapRequestBody,
    RoadmapResponseBody,
    RoadmapStep,
    ImageStatus,
    AccessGrantResult,
    AccessStatus,
    CreateChat,
    ConversationSummary,
    ConversationDetail,
)
import ingestion
import ml_retrieval
import access_service
import chat_repo
import db_init
from account import resolve_account

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


# Register ChatLens-owned Calendar + Tasks routes (P2S4). Additive: does not
# alter any existing route or retrieval/search behavior. Guarded so a calendar/
# task import problem never crashes the whole app at startup (dev-safe).
try:
    from calendar_tasks.routes import register_calendar_tasks_routes
    register_calendar_tasks_routes(app)
except Exception as e:  # noqa: BLE001
    print(f"[calendar_tasks] route registration failed: {e}")

# Register the narrow, validated agent-action seam (P2S5) so confirmed
# Add Calendar / Add Task actions dispatch through the existing orchestrator.
try:
    from calendar_tasks.agent_routes import register_agent_action_routes
    register_agent_action_routes(app)
except Exception as e:  # noqa: BLE001
    print(f"[calendar_tasks] agent-action route registration failed: {e}")


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
def summarize_images(
    request: SummarizeRequestBody,
    account: str = Depends(resolve_account),
):
    # P2S5.1: connect to the EXISTING summarize agent (local Qwen) via the
    # deterministic action router. mode = summary | key_points | roadmap. The
    # selected memories' real OCR/extracted text is gathered from the existing
    # retrieval seam; missing text yields a controlled (non-hallucinating) msg.
    import memory_actions
    action = (request.mode or "summary")
    result = memory_actions.run_summary_action(account, request.imageIds, action)
    data = result.get("data") or {}
    used = (result.get("metadata") or {}).get("used_image_ids") or []
    return SummaryResponseBody(
        sessionId=request.sessionId,
        summary=(data.get("summary") or result.get("message") or ""),
        usedImageIds=used,
        points=(data.get("points") or data.get("steps") or None),
        ok=bool(result.get("ok")),
        mode=data.get("mode") or action,
    )


@app.post("/api/actions/roadmap", response_model=RoadmapResponseBody)
def generate_roadmap(
    request: RoadmapRequestBody,
    account: str = Depends(resolve_account),
):
    # P2S5.1: revision-roadmap via the EXISTING summarize agent (mode=roadmap),
    # grounded in the selected memories' real OCR text. No fabrication when no
    # text is available (returns an empty step list).
    import memory_actions
    result = memory_actions.run_summary_action(account, request.imageIds, "roadmap")
    steps_raw = (result.get("data") or {}).get("steps") or []
    steps = [RoadmapStep(order=i + 1, title=t) for i, t in enumerate(steps_raw)]
    return RoadmapResponseBody(sessionId=request.sessionId, steps=steps)


@app.post("/api/actions/related", response_model=List[MemoryResult])
def related_memories(
    request: RelatedMemoriesRequestBody,
    account: str = Depends(resolve_account),
):
    # P2S5.1: "Related Memories" reuses the EXISTING retrieval seam
    # (ml_retrieval.search_memories). NO new agent, NO new retrieval system.
    # The selected image is excluded from the returned list.
    import memory_actions
    result = memory_actions.run_related_memories(account, request.imageId, request.query)
    raw = result.get("raw") or []
    return [_build_memory_result(r) for r in raw]


@app.post("/api/actions/analyze_bill")
def analyze_bill_action(
    request: AnalyzeBillRequestBody,
    account: str = Depends(resolve_account),
):
    # P2S: Finance/Receipt agent over a selected memory. Supports plain analysis
    # (operation="analyze", default) and bill splitting (operation="split").
    # Reuses the EXISTING analyze_bill agent + OCR context. Never invents values;
    # returns the structured AgentResult (fields + optional split). Read-only.
    import memory_actions
    extra = {
        "operation": request.operation or "analyze",
        "split_mode": request.splitMode or "equal",
    }
    if request.ocrText:
        extra["ocr_text"] = request.ocrText
    if request.people is not None:
        extra["people"] = request.people
    if request.assignments is not None:
        extra["assignments"] = request.assignments
    if request.sharedItems is not None:
        extra["shared_items"] = request.sharedItems
    if request.tip is not None:
        extra["tip"] = request.tip
    result = memory_actions.run_analyze_bill(account, request.imageIds, extra)
    if not result.get("ok"):
        # Controlled agent failure -> 422 with the safe explanation, but still
        # return the structured body so the UI can show what's missing.
        raise HTTPException(status_code=422, detail=result.get("message") or "Bill analysis failed")
    return result


@app.post("/api/actions/research")
def research_action(
    request: ResearchRequestBody,
    account: str = Depends(resolve_account),
):
    # P3S1: credible multi-source research via the EXISTING Research agent
    # (scholarly providers + local Qwen synthesis). Account-scoped. Never
    # generates an answer when the agent reports no evidence. No secrets exposed.
    import memory_actions
    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="A research query is required.")
    result = memory_actions.run_research(
        account, query, max_results=request.maxResults, providers=request.providers,
    )
    if not result.get("ok"):
        err = result.get("error") or ""
        # Missing query is a 400; everything else (no_evidence / llm_error /
        # aggregation_error / provider issues) is a controlled 422 that still
        # carries the structured body (sources/limitations) for the UI.
        status = 400 if err == "no_query" else 422
        raise HTTPException(status_code=status, detail=result.get("message") or "Research failed")
    return result


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
def get_image_file(image_id: str):
    # Read-only serving of an already-indexed local image, resolved from the
    # canonical ML/Chroma record by its path-hash id. Never accepts a client
    # path; resolve_image_path validates existence, image type, and that the
    # file is within its authorized indexed location.
    #
    # NOTE: This GET is intentionally NOT gated by the X-Account-Id header.
    # Browsers cannot attach that custom header to a plain <img src> request, so
    # requiring it made every result image fail to load (401). The header is a
    # dev-only, spoofable attribution signal (see account.py) and was never used
    # to scope the served bytes here: resolve_image_path resolves purely by the
    # path-hash image_id and enforces its own existence/type/traversal checks.
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
