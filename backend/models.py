from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from database import Base

class Image(Base):
    __tablename__ = "images"

    id = Column(String, primary_key=True, index=True)
    original_filename = Column(String)
    stored_path = Column(String)
    source = Column(String, nullable=True)
    mime_type = Column(String)
    file_size = Column(Integer)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    captured_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime)
    processing_status = Column(String) # pending | processing | ready | failed
    processing_error = Column(String, nullable=True)

class ImageText(Base):
    __tablename__ = "image_texts"
    
    image_id = Column(String, ForeignKey("images.id"), primary_key=True)
    ocr_text = Column(String)
    ocr_engine = Column(String)
    processed_at = Column(DateTime)

class ImageEmbedding(Base):
    __tablename__ = "image_embeddings"
    
    image_id = Column(String, ForeignKey("images.id"), primary_key=True)
    embedding_model = Column(String)
    vector_store_id = Column(String)
    processed_at = Column(DateTime)

class SearchSession(Base):
    __tablename__ = "search_sessions"
    
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    active_query = Column(String)

class SearchMessage(Base):
    __tablename__ = "search_messages"
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("search_sessions.id"))
    role = Column(String) # user | assistant
    content = Column(String)
    created_at = Column(DateTime)

class SearchContext(Base):
    __tablename__ = "search_contexts"
    
    session_id = Column(String, ForeignKey("search_sessions.id"), primary_key=True)
    original_intent = Column(String)
    topic_clues = Column(String)
    content_clues = Column(String)
    visual_clues = Column(String)
    metadata_filters = Column(String)
    updated_query = Column(String)
