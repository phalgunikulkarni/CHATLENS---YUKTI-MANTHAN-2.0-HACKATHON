from datetime import datetime
from typing import Optional, Dict, Any, List
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
