import os
import uuid
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
import requests
from sqlalchemy.orm import Session
from googleapiclient.discovery import build

from connectors.google.google_auth import get_credentials
from models import Connector, Image

logger = logging.getLogger(__name__)

IMAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "images"))

class GooglePhotosDownloader:
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.credentials = get_credentials(account_id)
        if not self.credentials:
            raise ValueError("User is not authorized. Please authenticate first.")
            
        self.service = build('photoslibrary', 'v1', credentials=self.credentials, static_discovery=False)

    def fetch_items(self, limit: int = 10) -> List[Dict[str, Any]]:
        os.makedirs(IMAGE_DIR, exist_ok=True)
        items = []
        
        try:
            results = self.service.mediaItems().list(pageSize=limit).execute()
            media_items = results.get('mediaItems', [])
            
            for item in media_items:
                mime_type = item.get('mimeType', '')
                if not mime_type.startswith('image/'):
                    continue
                    
                download_url = item['baseUrl'] + '=d'
                msg_id = item['id']
                file_path = os.path.join(IMAGE_DIR, f"{msg_id}.jpg")
                
                response = requests.get(download_url)
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                        
                    items.append({
                        "file_path": os.path.abspath(file_path),
                        "source": "google",
                        "metadata": {
                            "message_id": msg_id,
                            "filename": item.get('filename'),
                            "date": item.get('mediaMetadata', {}).get('creationTime')
                        }
                    })
        except Exception as e:
            logger.error(f"Error fetching Google Photos items: {e}")
            raise e
            
        return items

def run_sync_job(account_id: str, db_session: Session) -> Dict[str, Any]:
    connector = db_session.query(Connector).filter(Connector.user_phone == account_id).first()
    if not connector:
        connector = Connector(
            id=str(uuid.uuid4()),
            user_phone=account_id,
            connector_type="google",
            status="connected",
            last_sync_message_id=0
        )
        db_session.add(connector)
        db_session.commit()
        db_session.refresh(connector)

    downloader = GooglePhotosDownloader(account_id)
    items = downloader.fetch_items(limit=10)

    try:
        from ml.pipeline.indexer import LibraryIndexer
        indexer = LibraryIndexer()
    except Exception as e:
        logger.error(f"Failed to import indexer: {e}")
        indexer = None

    indexed_count = 0

    for item in items:
        file_path = item["file_path"]
        meta = item["metadata"]

        image_id = str(uuid.uuid4())
        
        db_image = Image(
            id=image_id,
            original_filename=os.path.basename(file_path),
            stored_path=file_path,
            source="google",
            mime_type="image/jpeg",
            file_size=os.path.getsize(file_path),
            created_at=datetime.now(timezone.utc),
            processing_status="ready",
            source_type="google",
            source_metadata=str(meta)
        )
        db_session.add(db_image)

        if indexer:
            try:
                indexer.index_locations([file_path], account_id=account_id)
            except Exception as e:
                logger.error(f"Failed to index {file_path}: {e}")

        indexed_count += 1

    db_session.commit()

    return {"status": "success", "images_indexed": indexed_count}
