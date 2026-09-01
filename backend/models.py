from sqlalchemy import Column, String, DateTime
from database import Base

class Image(Base):
    __tablename__ = "images"

    image_id = Column(String, primary_key=True, index=True)
    image_reference = Column(String)
    source = Column(String)
    timestamp = Column(DateTime)
    ocr_text = Column(String, nullable=True)
    metadata_json = Column(String, nullable=True)
