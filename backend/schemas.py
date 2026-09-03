from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

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

class SearchRequest(BaseModel):
    query: str
    limit: int = 10

class SearchResult(BaseModel):
    image_id: str
    score: float
    thumbnail_or_image_url: str
    matched_signals: List[str]

class SearchResponse(BaseModel):
    session_id: str
    effective_query: str
    results: List[SearchResult]

class MessageRequest(BaseModel):
    message: str

class ExplanationResponse(BaseModel):
    explanation: str

class SummarizeRequest(BaseModel):
    image_ids: List[str]

class SummarizeResponse(BaseModel):
    summary: str

class RoadmapRequest(BaseModel):
    image_ids: List[str]

class RoadmapResponse(BaseModel):
    roadmap: str
