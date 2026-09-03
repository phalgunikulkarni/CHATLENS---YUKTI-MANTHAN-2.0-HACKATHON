from sqlalchemy.orm import Session
import models
from processing.embedding_service import embedding_service
from processing.vector_store import vector_store

def hybrid_search(db: Session, query: str, limit: int = 10):
    # 1. Visual Retrieval
    try:
        text_emb = embedding_service.process_text_embedding(query)
        distances, faiss_ids = vector_store.search_vectors(text_emb, top_k=limit*2)
    except Exception as e:
        print(f"Visual search failed: {e}")
        distances, faiss_ids = [], []
        
    visual_candidates = {}
    for dist, fid in zip(distances, faiss_ids):
        if fid != -1:
            # L2 distance for normalized vectors is 2 - 2*cos_sim
            # So cos_sim = 1 - (dist / 2). Clamp between 0.0 and 1.0.
            score = max(0.0, 1.0 - (dist / 2.0))
            
            # Map faiss ID back to image ID using ImageEmbedding table
            emb_record = db.query(models.ImageEmbedding).filter(models.ImageEmbedding.vector_store_id == str(fid)).first()
            if emb_record:
                visual_candidates[emb_record.image_id] = score
                
    # 2. Text Retrieval
    text_candidates = {}
    ocr_matches = {}
    search_term = f"%{query}%"
    text_records = db.query(models.ImageText).filter(models.ImageText.ocr_text.ilike(search_term)).limit(limit*2).all()
    for rec in text_records:
        text_candidates[rec.image_id] = 1.0
        ocr_matches[rec.image_id] = [query] # Just returning the exact query as a match for now
        
    # 3. Hybrid Scoring
    all_image_ids = set(visual_candidates.keys()).union(set(text_candidates.keys()))
    
    results = []
    for image_id in all_image_ids:
        v_score = visual_candidates.get(image_id, 0.0)
        t_score = text_candidates.get(image_id, 0.0)
        
        final_score = (0.6 * v_score) + (0.4 * t_score)
        
        signals = {
            "visual_score": v_score,
            "text_score": t_score,
            "ocr_matches": ocr_matches.get(image_id, [])
        }
        
        results.append({
            "image_id": image_id,
            "final_score": final_score,
            "signals": signals
        })
        
    # Sort descending
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[:limit]
