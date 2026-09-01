import json
import uuid
from typing import List
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import schemas
from retrieval import hybrid_search
import models
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ChatLens API", description="AI-powered personal visual memory search engine")

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

@app.post("/images", response_model=schemas.ImageResponse)
def upload_image(request: schemas.ImageUploadRequest, db: Session = Depends(get_db)):
    # Stubbed file saving and AI processing. 
    image_id = f"img_{uuid.uuid4().hex[:8]}"
    meta_json = json.dumps(request.metadata) if request.metadata else None
    
    db_image = models.Image(
        image_id=image_id,
        image_reference=request.image_reference,
        source=request.source,
        timestamp=request.timestamp,
        ocr_text="Mock OCR text generated upon upload",
        metadata_json=meta_json
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    meta = json.loads(db_image.metadata_json) if db_image.metadata_json else None
    return schemas.ImageResponse(
        image_id=db_image.image_id,
        image_reference=db_image.image_reference,
        source=db_image.source,
        timestamp=db_image.timestamp,
        ocr_text=db_image.ocr_text,
        metadata=meta,
        processing_state="completed"
    )

@app.get("/images", response_model=List[schemas.ImageResponse])
def list_images(db: Session = Depends(get_db)):
    results = db.query(models.Image).all()
    images = []
    for r in results:
        meta = json.loads(r.metadata_json) if r.metadata_json else None
        images.append(schemas.ImageResponse(
            image_id=r.image_id,
            image_reference=r.image_reference,
            source=r.source,
            timestamp=r.timestamp,
            ocr_text=r.ocr_text,
            metadata=meta,
            processing_state="completed"
        ))
    return images

@app.get("/images/{image_id}", response_model=schemas.ImageResponse)
def get_image(image_id: str, db: Session = Depends(get_db)):
    r = db.query(models.Image).filter(models.Image.image_id == image_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Image not found")
    meta = json.loads(r.metadata_json) if r.metadata_json else None
    return schemas.ImageResponse(
        image_id=r.image_id,
        image_reference=r.image_reference,
        source=r.source,
        timestamp=r.timestamp,
        ocr_text=r.ocr_text,
        metadata=meta,
        processing_state="completed"
    )

@app.post("/search", response_model=schemas.SearchResponse)
def search(request: schemas.SearchRequest, db: Session = Depends(get_db)):
    # Stubbed to call retrieval.py text search
    results = hybrid_search(db, request.query)
    
    search_results = []
    for r in results:
        img_resp = schemas.ImageResponse(
            image_id=r.image_id,
            image_reference=r.image_reference,
            source=r.source,
            timestamp=r.timestamp,
            ocr_text=r.ocr_text,
            metadata=r.metadata,
            processing_state="completed"
        )
        search_results.append(schemas.SearchResult(
            image=img_resp,
            score=0.95,
            signals={"ocr_match": True, "semantic_similarity": 0.8}
        ))
    return schemas.SearchResponse(results=search_results)

@app.post("/conversations/{conversation_id}/messages", response_model=schemas.SearchResponse)
def add_message(conversation_id: str, request: schemas.MessageRequest, db: Session = Depends(get_db)):
    # Stubbed conversational refinement
    results = hybrid_search(db, request.message)
    
    search_results = []
    for r in results:
        img_resp = schemas.ImageResponse(
            image_id=r.image_id,
            image_reference=r.image_reference,
            source=r.source,
            timestamp=r.timestamp,
            ocr_text=r.ocr_text,
            metadata=r.metadata,
            processing_state="completed"
        )
        search_results.append(schemas.SearchResult(
            image=img_resp,
            score=0.98,
            signals={"clue_match": True, "conversational_context": 0.9}
        ))
    return schemas.SearchResponse(results=search_results)

@app.get("/search-results/{result_id}/explanation", response_model=schemas.ExplanationResponse)
def get_explanation(result_id: str):
    # Stubbed explanation
    return schemas.ExplanationResponse(
        explanation="Matched based on OCR text and semantic similarity to your requested memory clues.",
        evidence_signals={"ocr_matched_terms": ["python", "error"], "semantic_score": 0.88, "visual_match": False}
    )

@app.post("/actions/summarize", response_model=schemas.SummarizeResponse)
def summarize_images(request: schemas.SummarizeRequest):
    # Stubbed summarization
    return schemas.SummarizeResponse(
        summary=f"This is a mock AI summary of {len(request.image_ids)} images. It extracts the core themes and facts across the selected visual memories."
    )

@app.post("/actions/roadmap", response_model=schemas.RoadmapResponse)
def generate_roadmap(request: schemas.RoadmapRequest):
    # Stubbed roadmap generation
    goal_text = f" to achieve: {request.goal}" if request.goal else ""
    return schemas.RoadmapResponse(
        roadmap=f"Mock actionable roadmap{goal_text}:\n1. Review the retrieved visual notes.\n2. Synthesize information into a document.\n3. Execute the next steps."
    )
