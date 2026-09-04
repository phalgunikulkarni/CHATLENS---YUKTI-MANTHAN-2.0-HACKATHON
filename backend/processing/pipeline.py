from sqlalchemy.orm import Session
from datetime import datetime, timezone
import models
from processing.ocr_service import ocr_service
from processing.embedding_service import embedding_service
from processing.vector_store import vector_store
import traceback
from database import SessionLocal

def process_image_task(image_id: str):
    db = SessionLocal()
    try:
        db_image = db.query(models.Image).filter(models.Image.id == image_id).first()
        if not db_image:
            return
            
        db_image.processing_status = "processing"
        db.commit()
        
        # 1. OCR
        ocr_result = ocr_service.extract_text(db_image.stored_path)
        if ocr_result:
            image_text = models.ImageText(
                image_id=image_id,
                ocr_text=ocr_result,
                ocr_engine="easyocr",
                processed_at=datetime.now(timezone.utc)
            )
            db.add(image_text)
            
        # 2. Embedding
        faiss_id = embedding_service.process_image_embedding(db_image.stored_path, vector_store)
        image_embedding = models.ImageEmbedding(
            image_id=image_id,
            embedding_model="openai/clip-vit-base-patch32",
            vector_store_id=faiss_id,
            processed_at=datetime.now(timezone.utc)
        )
        db.add(image_embedding)
        
        db_image.processing_status = "ready"
        db.commit()
        
    except Exception as e:
        db.rollback()
        db_image = db.query(models.Image).filter(models.Image.id == image_id).first()
        if db_image:
            db_image.processing_status = "failed"
            db_image.processing_error = str(e)
            db.commit()
        print(f"Processing failed for {image_id}: {traceback.format_exc()}")
    finally:
        db.close()
