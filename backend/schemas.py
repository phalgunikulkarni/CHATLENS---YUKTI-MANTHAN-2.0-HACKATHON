from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel

class ImageRecord(BaseModel):
    image_id: str
    image_reference: str
    source: str
    timestamp: datetime
    ocr_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ImageResponse(BaseModel):
    image_id: str
    image_reference: str
    source: str
    timestamp: datetime
    ocr_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    processing_state: str = "completed"

class ImageUploadRequest(BaseModel):
    image_reference: str
    source: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str

class SearchResult(BaseModel):
    image: ImageResponse
    score: float
    signals: Dict[str, Any]

class SearchResponse(BaseModel):
    results: List[SearchResult]

class MessageRequest(BaseModel):
    message: str

class ExplanationResponse(BaseModel):
    explanation: str
    evidence_signals: Dict[str, Any]

class SummarizeRequest(BaseModel):
    image_ids: List[str]

class SummarizeResponse(BaseModel):
    summary: str

class RoadmapRequest(BaseModel):
    image_ids: List[str]
    goal: Optional[str] = None

class RoadmapResponse(BaseModel):
    roadmap: str

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
    sourceTag: Optional[str] = None
    capturedAt: Optional[str] = None
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

class SummaryResponseBody(BaseModel):
    sessionId: str
    summary: str
    usedImageIds: List[str]

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
