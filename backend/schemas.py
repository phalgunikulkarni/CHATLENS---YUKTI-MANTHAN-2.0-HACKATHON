from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel


class ImageResponse(BaseModel):
    id: str
    original_filename: str
    stored_path: str
    source: Optional[str] = None
    mime_type: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    captured_at: Optional[datetime] = None
    created_at: datetime
    processing_status: str
    processing_error: Optional[str] = None

# ---------------------------------------------------------------------------
# Frontend-canonical models
#
# Field names below are intentionally camelCase to match the frontend
# TypeScript contract. FastAPI serializes field names as-is, so naming the
# Python fields in camelCase produces the JSON shape the frontend expects.
# ---------------------------------------------------------------------------

class ExplanationSignal(BaseModel):
    type: str  # one of ocr|semantic|visual|metadata|clue (str to stay permissive)
    label: str
    icon: str
    strength: Optional[float] = None

class MemoryClue(BaseModel):
    id: str
    label: str

class MemoryResult(BaseModel):
    # Frontend interface name is `SearchResult`; distinct Python class name
    # avoids clashing with the legacy `SearchResult` model above.
    id: str
    thumbnailUrl: str
    fullUrl: Optional[str] = None
    ocrSnippet: Optional[str] = None
    matchScore: Optional[float] = None
    similarity: Optional[int] = None  # 0-100 truthful similarity from real cosine signals
    sourceTag: Optional[str] = None
    capturedAt: Optional[str] = None
    # BLIP-generated natural-language visual description (from ingestion),
    # carried through from the stored Chroma visual metadata. None when absent;
    # never fabricated. Does not affect ranking/similarity/ordering.
    visualDescription: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
    explanation: Optional[List[ExplanationSignal]] = None

class TurnResponse(BaseModel):
    sessionId: str
    intent: Optional[str] = None  # search|refinement|explanation|summarize|roadmap|schedule
    agentMessage: str
    clues: Optional[List[MemoryClue]] = None
    results: Optional[List[MemoryResult]] = None

class TurnSearchRequest(BaseModel):
    query: str
    sessionId: Optional[str] = None

class RefineRequestBody(BaseModel):
    message: str
    sessionId: str
    activeClues: List[MemoryClue] = []

class SummarizeRequestBody(BaseModel):
    sessionId: str
    imageIds: List[str]
    # P2S5.1: which selected-memory action this is. summary|key_points|roadmap.
    mode: Optional[str] = "summary"

class SummaryResponseBody(BaseModel):
    sessionId: str
    summary: str
    usedImageIds: List[str]
    # P2S5.1: optional structured extras (key points / roadmap steps as strings).
    points: Optional[List[str]] = None
    ok: bool = True
    mode: Optional[str] = "summary"

class RelatedMemoriesRequestBody(BaseModel):
    sessionId: str
    imageId: str
    query: Optional[str] = None

class ResearchRequestBody(BaseModel):
    sessionId: Optional[str] = None
    query: str
    maxResults: Optional[int] = None
    providers: Optional[List[str]] = None

class AnalyzeBillRequestBody(BaseModel):
    sessionId: str
    imageIds: List[str] = []
    # Optional raw OCR text (selected-memory flow may pass it directly).
    ocrText: Optional[str] = None
    # "analyze" (default) or "split".
    operation: Optional[str] = "analyze"
    # Split params (only used when operation == "split").
    splitMode: Optional[str] = "equal"   # equal | items
    people: Optional[int] = None
    assignments: Optional[Dict[str, List[int]]] = None
    sharedItems: Optional[List[int]] = None
    tip: Optional[float] = None

class RoadmapStep(BaseModel):
    order: int
    title: str
    detail: Optional[str] = None

class RoadmapRequestBody(BaseModel):
    sessionId: str
    imageIds: List[str]

class RoadmapResponseBody(BaseModel):
    sessionId: str
    steps: List[RoadmapStep]

class ImageStatus(BaseModel):
    imageId: str
    status: str  # uploaded|processing|indexed|ready|failed

class AccessGrantResult(BaseModel):
    authorized: bool
    roots: List[str] = []
    message: str

class AccessStatus(BaseModel):
    authorized: bool
    indexing: str           # idle | running | ready | failed
    roots: List[str] = []
    indexedCount: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Chat persistence DTOs (Phase B)
#
# camelCase to match the frontend TypeScript contract (consistent with the
# frontend-canonical models above). TurnResponse is intentionally NOT changed.
# ---------------------------------------------------------------------------

class CreateChat(BaseModel):
    # Optional client-supplied title; the session id is always backend-authoritative.
    title: Optional[str] = None


class ConversationSummary(BaseModel):
    sessionId: str
    title: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class ResultRef(BaseModel):
    # Display-safe only: image_id + rank + display metadata. No paths, no binaries.
    imageId: str
    rank: int
    displayMetadata: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    id: str
    role: str  # user | assistant
    content: str
    createdAt: Optional[str] = None
    results: List[ResultRef] = []


class ConversationDetail(BaseModel):
    sessionId: str
    title: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    messages: List[ChatMessage] = []
    context: Optional[Dict[str, Any]] = None
