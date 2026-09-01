import json
from typing import List
from sqlalchemy.orm import Session
from models import Image
from schemas import ImageRecord

def hybrid_search(db: Session, query: str) -> List[ImageRecord]:
    """
    Search SQLite database for images where ocr_text contains the query.
    """
    search_query = f"%{query}%"
    results = db.query(Image).filter(Image.ocr_text.ilike(search_query)).all()
    
    image_records = []
    for r in results:
        meta = json.loads(r.metadata_json) if r.metadata_json else None
        image_records.append(ImageRecord(
            image_id=r.image_id,
            image_reference=r.image_reference,
            source=r.source,
            timestamp=r.timestamp,
            ocr_text=r.ocr_text,
            metadata=meta
        ))
    return image_records
