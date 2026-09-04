import os
import uuid
import shutil
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from PIL import Image as PILImage
import models

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage", "images")
os.makedirs(STORAGE_DIR, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024 # 10 MB
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"]

def save_uploaded_image(db: Session, file: UploadFile, source: str = None) -> models.Image:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPEG, PNG, and WebP are allowed.")
    
    # Read file size to check limit
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
        
    image_id = str(uuid.uuid4())
    
    ext = ".jpg"
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[1].lower()
    elif file.content_type == "image/png":
        ext = ".png"
    elif file.content_type == "image/webp":
        ext = ".webp"
        
    stored_filename = f"{image_id}{ext}"
    stored_path = os.path.join(STORAGE_DIR, stored_filename)
    
    with open(stored_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        with PILImage.open(stored_path) as img:
            width, height = img.size
    except Exception as e:
        os.remove(stored_path)
        raise HTTPException(status_code=400, detail="Invalid image file.")
        
    db_image = models.Image(
        id=image_id,
        original_filename=file.filename or "unknown",
        stored_path=stored_path,
        source=source,
        mime_type=file.content_type,
        file_size=file_size,
        width=width,
        height=height,
        captured_at=None,
        created_at=datetime.now(timezone.utc),
        processing_status="pending"
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    return db_image
