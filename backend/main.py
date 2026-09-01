import json
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from schemas import SearchQuery, ImageRecord
from retrieval import hybrid_search
import models
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ChatLens API")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/images/")
def create_image(image: ImageRecord, db: Session = Depends(get_db)):
    meta_json = json.dumps(image.metadata) if image.metadata else None
    db_image = models.Image(
        image_id=image.image_id,
        image_reference=image.image_reference,
        source=image.source,
        timestamp=image.timestamp,
        ocr_text=image.ocr_text,
        metadata_json=meta_json
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return {"status": "success", "image_id": db_image.image_id}

@app.post("/search")
def search(query_request: SearchQuery, db: Session = Depends(get_db)):
    results = hybrid_search(db, query_request.query)
    
    return {
        "results": results,
        "explanation": f"Matched based on OCR text containing '{query_request.query}'."
    }
