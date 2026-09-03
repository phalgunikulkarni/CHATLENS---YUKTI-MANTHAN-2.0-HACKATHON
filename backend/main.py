from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from database import engine, SessionLocal
from schemas import (
    SearchRequest, SearchResponse, MessageRequest, 
    ExplanationResponse, SummarizeRequest, SummarizeResponse,
    RoadmapRequest, RoadmapResponse, ImageResponse
)
from datetime import datetime
import uuid
import ingestion

# Create tables in SQLite
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ChatLens API")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health_check():
    return {"status": "ok"}

from fastapi import BackgroundTasks

@app.post("/images", response_model=ImageResponse)
def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...), source: str = Form(None), db: Session = Depends(get_db)):
    db_image = ingestion.save_uploaded_image(db, file, source)
    
    # Trigger background processing
    from processing.pipeline import process_image_task
    background_tasks.add_task(process_image_task, db_image.id)
    
    return db_image

@app.get("/images/{image_id}", response_model=ImageResponse)
def get_image(image_id: str, db: Session = Depends(get_db)):
    db_image = db.query(models.Image).filter(models.Image.id == image_id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")
    return db_image

@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, db: Session = Depends(get_db)):
    from retrieval.engine import hybrid_search
    from schemas import SearchResult
    
    # Track the session
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    db_session = models.SearchSession(id=session_id, created_at=now, updated_at=now, active_query=request.query)
    db_context = models.SearchContext(session_id=session_id, original_intent=request.query, updated_query=request.query)
    
    db.add(db_session)
    db.add(db_context)
    db.commit()
    
    # Run retrieval
    raw_results = hybrid_search(db, request.query, request.limit)
    
    results = []
    for r in raw_results:
        # We'll stub thumbnail_or_image_url for now since we don't have a serve route for images yet
        img = db.query(models.Image).filter(models.Image.id == r["image_id"]).first()
        url = f"/images/{r['image_id']}/file" if img else ""
        
        # We map OCR matches to strings for the matched_signals array to fit our schema
        matched_signals = []
        if r["signals"]["visual_score"] > 0:
            matched_signals.append(f"Visual Score: {r['signals']['visual_score']:.2f}")
        if r["signals"]["text_score"] > 0:
            matched_signals.append(f"Text Score: {r['signals']['text_score']:.2f}")
            if r["signals"]["ocr_matches"]:
                matched_signals.append(f"OCR Matched: {r['signals']['ocr_matches'][0]}")
                
        results.append(SearchResult(
            image_id=r["image_id"],
            score=r["final_score"],
            thumbnail_or_image_url=url,
            matched_signals=matched_signals
        ))
        
    return SearchResponse(
        session_id=session_id,
        effective_query=request.query,
        results=results
    )

@app.post("/search-sessions/{session_id}/messages", response_model=SearchResponse)
def refine_search(session_id: str, request: MessageRequest):
    # Stub response
    return SearchResponse(
        session_id=session_id,
        effective_query="updated mock query based on refinement",
        results=[]
    )

@app.get("/search-results/{result_id}/explanation", response_model=ExplanationResponse)
def get_explanation(result_id: str):
    # Stub response
    return ExplanationResponse(explanation="Mock explanation for retrieving result.")

@app.post("/actions/summarize", response_model=SummarizeResponse)
def summarize(request: SummarizeRequest):
    # Stub response
    return SummarizeResponse(summary="Mock summary of the selected memories.")

@app.post("/actions/roadmap", response_model=RoadmapResponse)
def roadmap(request: RoadmapRequest):
    # Stub response
    return RoadmapResponse(roadmap="Mock roadmap:\n1. Step one\n2. Step two")
