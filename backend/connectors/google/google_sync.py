"""Google Photos Picker-based sync for ChatLens.

The legacy library-scan path (mediaItems.list under photoslibrary.readonly) is
DEAD as of 2025-03-31. This module drives the user-consented **Picker API**
instead:

  1. Create a picker session   -> POST /v1/sessions  (returns pickerUri)
  2. User selects photos        -> in the Google-hosted picker (pickerUri)
  3. Poll the session           -> GET /v1/sessions/{id} until mediaItemsSet
  4. List picked media items    -> GET /v1/mediaItems?sessionId=... (paginated)
  5. Download bytes             -> GET mediaFile.baseUrl + "=d"
  6. Index via the EXISTING LibraryIndexer (no second pipeline / VLM)

The existing entrypoint `run_sync_job(account_id, db_session)` is preserved. It
now returns the pickerUri so the frontend can open it, then polls, downloads,
dedups, and indexes. Token values and secrets are never logged.
"""

import os
import json
import time
import hashlib
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import requests
from sqlalchemy.orm import Session

from connectors.google.google_auth import get_credentials, GoogleAuthError
from models import Connector, Image

logger = logging.getLogger(__name__)

IMAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "images"))

PICKER_BASE = "https://photospicker.googleapis.com/v1"

# Only these image MIME types are imported; the real type is preserved on the row.
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Allowed configurable import limits; anything else clamps to the nearest sane default.
ALLOWED_LIMITS = (10, 25, 50, 100)
DEFAULT_LIMIT = int(os.environ.get("GOOGLE_IMPORT_LIMIT", "25"))

# How long to wait for the user to finish picking (seconds) and poll interval.
PICKER_POLL_TIMEOUT = int(os.environ.get("GOOGLE_PICKER_POLL_TIMEOUT", "300"))
PICKER_POLL_INTERVAL = int(os.environ.get("GOOGLE_PICKER_POLL_INTERVAL", "3"))


def _resolve_limit(limit: Optional[int]) -> int:
    if limit is None:
        limit = DEFAULT_LIMIT
    if limit in ALLOWED_LIMITS:
        return limit
    # Clamp to the closest allowed value (keeps demos predictable).
    return min(ALLOWED_LIMITS, key=lambda v: abs(v - limit))


class GooglePickerClient:
    """Thin REST client over the Picker API using a Bearer access token.

    Uses plain `requests` (simpler than the discovery client for the Picker
    endpoints). The Authorization header carries the token; it is never logged.
    """

    def __init__(self, access_token: str, session: Optional[requests.Session] = None):
        self._token = access_token
        self._http = session or requests.Session()

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def create_session(self) -> Dict[str, Any]:
        resp = self._http.post(f"{PICKER_BASE}/sessions", headers=self._headers(), json={})
        resp.raise_for_status()
        return resp.json()

    def get_session(self, session_id: str) -> Dict[str, Any]:
        resp = self._http.get(f"{PICKER_BASE}/sessions/{session_id}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def list_media_items(self, session_id: str, page_token: Optional[str] = None,
                         page_size: int = 100) -> Dict[str, Any]:
        params = {"sessionId": session_id, "pageSize": page_size}
        if page_token:
            params["pageToken"] = page_token
        resp = self._http.get(f"{PICKER_BASE}/mediaItems", headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def download_bytes(self, base_url: str) -> bytes:
        # "=d" downloads the original bytes (Exif minus location) per Picker docs.
        resp = self._http.get(base_url + "=d", headers=self._headers())
        resp.raise_for_status()
        return resp.content

    def delete_session(self, session_id: str) -> None:
        try:
            self._http.delete(f"{PICKER_BASE}/sessions/{session_id}", headers=self._headers())
        except Exception:  # noqa: BLE001 - cleanup is best-effort
            logger.info("Picker session cleanup skipped.")


def _ext_for_mime(mime_type: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(mime_type, ".jpg")


def _deterministic_filename(media_item_id: str, mime_type: str) -> str:
    """Collision-resistant, deterministic filename derived from the item id."""
    digest = hashlib.sha256(media_item_id.encode("utf-8")).hexdigest()[:32]
    return f"google_{digest}{_ext_for_mime(mime_type)}"


def _already_imported(db: Session, account_id: str, media_item_id: str) -> bool:
    """True if this google_media_item_id was already imported for this account.

    Matches on the JSON substring in source_metadata (source_metadata stores a
    JSON object that includes "google_media_item_id"). Scoped to google-source
    rows for this account so Telegram/local rows are never touched.
    """
    needle = f'"google_media_item_id": "{media_item_id}"'
    rows = (
        db.query(Image)
        .filter(Image.account_id == account_id, Image.source == "google")
        .all()
    )
    for row in rows:
        if row.source_metadata and needle in row.source_metadata:
            return True
    return False


def _poll_until_ready(client: GooglePickerClient, session_id: str,
                      timeout: int, interval: int) -> bool:
    """Poll the session until the user has finished selecting media items."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = client.get_session(session_id)
        if info.get("mediaItemsSet"):
            return True
        time.sleep(interval)
    return False


def _iter_picked_items(client: GooglePickerClient, session_id: str, limit: int) -> List[Dict[str, Any]]:
    """List picked items across all pages (nextPageToken), stopping at `limit`."""
    collected: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    while True:
        page = client.list_media_items(session_id, page_token=page_token, page_size=100)
        for item in page.get("mediaItems", []):
            collected.append(item)
            if len(collected) >= limit:
                return collected
        page_token = page.get("nextPageToken")
        if not page_token:
            break
    return collected


def _set_connector_status(db: Session, account_id: str, status: str) -> Connector:
    connector = db.query(Connector).filter(Connector.user_phone == account_id).first()
    if not connector:
        import uuid
        connector = Connector(
            id=str(uuid.uuid4()),
            user_phone=account_id,
            connector_type="google",
            status=status,
            last_sync_message_id=0,
        )
        db.add(connector)
    else:
        connector.status = status
    db.commit()
    db.refresh(connector)
    return connector


def _get_indexer():
    """Return the shared LibraryIndexer, or None if the ML stack is unavailable."""
    try:
        from ml.pipeline.indexer import LibraryIndexer
        return LibraryIndexer()
    except Exception as e:  # noqa: BLE001 - ML stack optional in some environments
        logger.error(f"LibraryIndexer unavailable: {e}")
        return None


def run_sync_job(account_id: str, db_session: Session, limit: Optional[int] = None,
                 client: Optional[GooglePickerClient] = None,
                 wait_for_selection: bool = True) -> Dict[str, Any]:
    """Run a Picker-based import for `account_id`.

    Preserves the original name/signature (account_id, db_session). `client` is
    injectable for tests. Returns real counts and a pickerUri the frontend opens
    so the user can select photos.
    """
    limit = _resolve_limit(limit)

    creds = None
    try:
        creds = get_credentials(account_id)
    except GoogleAuthError:
        # Revoked/failed refresh — mark error, do not loop-fail.
        _set_connector_status(db_session, account_id, "error")
        return {
            "status": "error",
            "error": "authorization",
            "total_processed": 0, "downloaded": 0, "duplicates_skipped": 0,
            "indexed": 0, "download_failures": 0, "index_failures": 0,
        }

    if creds is None:
        _set_connector_status(db_session, account_id, "error")
        return {
            "status": "error",
            "error": "not_authorized",
            "total_processed": 0, "downloaded": 0, "duplicates_skipped": 0,
            "indexed": 0, "download_failures": 0, "index_failures": 0,
        }

    if client is None:
        client = GooglePickerClient(creds.token)

    _set_connector_status(db_session, account_id, "syncing")
    os.makedirs(IMAGE_DIR, exist_ok=True)

    # 1) Create the picker session.
    session = client.create_session()
    session_id = session.get("id")
    picker_uri = session.get("pickerUri")

    # 2) Wait for the user to finish selecting in the Google-hosted picker.
    if wait_for_selection:
        ready = _poll_until_ready(client, session_id, PICKER_POLL_TIMEOUT, PICKER_POLL_INTERVAL)
        if not ready:
            _set_connector_status(db_session, account_id, "connected")
            return {
                "status": "error",
                "error": "picker_timeout",
                "pickerUri": picker_uri,
                "total_processed": 0, "downloaded": 0, "duplicates_skipped": 0,
                "indexed": 0, "download_failures": 0, "index_failures": 0,
            }

    # 3) List selected items (paginated), capped at limit.
    items = _iter_picked_items(client, session_id, limit)

    indexer = _get_indexer()

    total_processed = 0
    downloaded = 0
    duplicates_skipped = 0
    indexed = 0
    download_failures = 0
    index_failures = 0

    for item in items:
        media_item_id = item.get("id")
        media_file = item.get("mediaFile", {}) or {}
        mime_type = media_file.get("mimeType", "")
        base_url = media_file.get("baseUrl")
        filename = media_file.get("filename")

        # MIME filtering — only supported still images.
        if mime_type not in ALLOWED_MIME_TYPES:
            continue

        total_processed += 1

        # DEDUP — skip anything already imported for this account.
        if _already_imported(db_session, account_id, media_item_id):
            duplicates_skipped += 1
            continue

        # 5) Download bytes.
        stored_name = _deterministic_filename(media_item_id, mime_type)
        file_path = os.path.join(IMAGE_DIR, stored_name)
        try:
            content = client.download_bytes(base_url)
            with open(file_path, "wb") as f:
                f.write(content)
        except Exception as e:  # noqa: BLE001 - per-image failure, keep going
            download_failures += 1
            logger.error(f"Download failed for a Google media item: {type(e).__name__}")
            continue

        downloaded += 1

        # Store metadata as JSON (never str()); google_media_item_id replaces message_id.
        meta = {
            "google_media_item_id": media_item_id,
            "filename": filename,
            "date": (item.get("createTime")
                     or media_file.get("mediaFileMetadata", {}).get("creationTime")),
        }

        db_image = Image(
            id=media_item_id,
            original_filename=filename or stored_name,
            stored_path=os.path.abspath(file_path),
            source="google",
            mime_type=mime_type,  # preserve the real MIME type
            file_size=os.path.getsize(file_path),
            created_at=datetime.now(timezone.utc),
            processing_status="ready",
            source_type="google",
            source_metadata=json.dumps(meta),
            account_id=account_id,
        )
        db_session.add(db_image)
        db_session.commit()

        # 6) Index via the EXISTING pipeline. Failure is counted; not "indexed".
        if indexer is None:
            index_failures += 1
            continue
        try:
            indexer.index_locations([os.path.abspath(file_path)], account_id=account_id)
            indexed += 1
        except Exception as e:  # noqa: BLE001 - per-image indexing failure
            index_failures += 1
            logger.error(f"Indexing failed for a Google media item: {type(e).__name__}")

    # Best-effort session cleanup.
    if session_id:
        client.delete_session(session_id)

    if download_failures == 0 and index_failures == 0:
        status = "success"
    elif downloaded > 0 or indexed > 0:
        status = "partial"
    else:
        status = "error"

    _set_connector_status(db_session, account_id, "connected")

    return {
        "status": status,
        "pickerUri": picker_uri,
        "total_processed": total_processed,
        "downloaded": downloaded,
        "duplicates_skipped": duplicates_skipped,
        "indexed": indexed,
        "download_failures": download_failures,
        "index_failures": index_failures,
    }


def start_picker_session(account_id: str, db_session: Session,
                         client: Optional[GooglePickerClient] = None) -> Dict[str, Any]:
    """Create a picker session and return the pickerUri without blocking.

    Lets the frontend open the picker first, then call the sync to poll+import.
    """
    try:
        creds = get_credentials(account_id)
    except GoogleAuthError:
        _set_connector_status(db_session, account_id, "error")
        return {"status": "error", "error": "authorization"}
    if creds is None:
        return {"status": "error", "error": "not_authorized"}

    if client is None:
        client = GooglePickerClient(creds.token)

    session = client.create_session()
    _set_connector_status(db_session, account_id, "connected")
    return {
        "status": "ok",
        "sessionId": session.get("id"),
        "pickerUri": session.get("pickerUri"),
    }
