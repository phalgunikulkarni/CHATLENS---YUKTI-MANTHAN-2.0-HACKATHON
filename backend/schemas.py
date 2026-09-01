from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

class ImageRecord(BaseModel):
    image_id: str
    image_reference: str
    source: str
    timestamp: datetime
    ocr_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SearchQuery(BaseModel):
    query: str
