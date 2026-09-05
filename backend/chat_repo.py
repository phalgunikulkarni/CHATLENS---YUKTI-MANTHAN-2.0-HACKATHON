"""Account-scoped chat persistence repository (Phase B).

All chat reads/writes are ordinary SQLAlchemy queries against the revived
`search_sessions` / `search_messages` / `search_contexts` tables plus the new
`search_result_refs` table. Every public function takes an `account_id` and a
`db: Session` and restricts its work to that owner.

Ownership is enforced by `_owned_or_raise`, which raises:
  - HTTPException(404) when the session does not exist, and
  - HTTPException(403) when it exists but is owned by a different account.

This guarantees no cross-account read/write/delete is ever attempted, and never
a 200-with-empty substitute (the caller endpoints propagate these HTTP errors).

Result references persist ONLY display-safe fields (image_id, rank, and a small
display-metadata JSON). They intentionally exclude filesystem paths and binary
data (R4.5): keys named like path/absolute_path/file_path/source_root/binary are
stripped defensively before persistence, in addition to the storage model having
no such columns.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

import backend.models as models

# Keys that must never be persisted in a Result_Reference's display metadata.
_FORBIDDEN_META_KEYS = {
    "path",
    "file_path",
    "filepath",
    "absolute_path",
    "abspath",
    "source_root",
    "stored_path",
    "binary",
    "bytes",
    "data",
    "blob",
    "thumbnailurl",
    "fullurl",
    "thumbnail_url",
    "full_url",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_session_id() -> str:
    """Server-authoritative session id (opaque, server-minted)."""
    return f"session_{uuid.uuid4().hex}"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _safe_display_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ONLY display-safe fields from a raw result dict.

    Strips any key that looks like a filesystem path or binary payload (R4.5).
    Keeps small, displayable scalar metadata (filename, category, scores, etc.).
    """
    out: Dict[str, Any] = {}
    for key, value in (result or {}).items():
        if key is None:
            continue
        lname = str(key).lower()
        if lname in _FORBIDDEN_META_KEYS:
            continue
        if "path" in lname:  # defensive: never persist any *_path field
            continue
        if key in ("image_id", "id"):
            continue  # image_id stored in its own column, not display metadata
        # Only keep JSON-serializable, display-safe scalar values.
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
    return out


def _owned_or_raise(db: Session, account_id: str, session_id: str) -> models.SearchSession:
    """Return the session row owned by `account_id`, else raise.

    - 404 when the session does not exist.
    - 403 when it exists but is owned by a different account.
    """
    row = (
        db.query(models.SearchSession)
        .filter(models.SearchSession.id == session_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if row.account_id != account_id:
        raise HTTPException(status_code=403, detail="Conversation owned by another account")
    return row


# ---------------------------------------------------------------------------
# 2.4 — conversation creation + ownership helper
# ---------------------------------------------------------------------------

def create_conversation(db: Session, account_id: str, title: Optional[str] = None) -> str:
    """Create a new conversation owned solely by `account_id`; return its id.

    The session id is backend-authoritative. account_id is set to the resolved
    account and is never null/anonymous/previous/global. Existing conversations
    are not modified.
    """
    now = _now()
    session_id = _new_session_id()
    session = models.SearchSession(
        id=session_id,
        account_id=account_id,
        title=title,
        created_at=now,
        updated_at=now,
        active_query=None,
    )
    db.add(session)
    db.commit()
    return session_id


# ---------------------------------------------------------------------------
# 2.5 — persist search turns
# ---------------------------------------------------------------------------

def append_search_turn(
    db: Session,
    account_id: str,
    session_id: str,
    query: str,
    results: List[Dict[str, Any]],
) -> models.SearchMessage:
    """Persist a user search message + one result ref per result.

    Zero results -> a message with no refs. Raises via `_owned_or_raise` before
    persisting anything if the session is missing/cross-account.
    """
    session = _owned_or_raise(db, account_id, session_id)
    now = _now()

    message = models.SearchMessage(
        id=_new_id("msg"),
        session_id=session_id,
        account_id=account_id,
        role="user",
        content=query,
        created_at=now,
    )
    db.add(message)
    db.flush()  # ensure message.id is available for the refs' FK

    for rank, result in enumerate(results or []):
        image_id = (result or {}).get("image_id") or (result or {}).get("id")
        display_md = _safe_display_metadata(result)
        ref = models.SearchResultRef(
            id=_new_id("ref"),
            message_id=message.id,
            session_id=session_id,
            account_id=account_id,
            image_id=image_id,
            rank=rank,
            display_metadata_json=json.dumps(display_md),
        )
        db.add(ref)

    session.updated_at = now
    if query:
        session.active_query = query
    db.commit()
    return message


# ---------------------------------------------------------------------------
# 2.6 — persist refinement turns
# ---------------------------------------------------------------------------

def append_refine_turn(
    db: Session,
    account_id: str,
    session_id: str,
    message: str,
    clues: Optional[List[Dict[str, Any]]],
    results: List[Dict[str, Any]],
) -> models.SearchMessage:
    """Append a refinement message (+ clues/context + result refs) to an owned
    conversation. Does NOT create a new conversation. Cross-account/nonexistent
    -> 403/404 with nothing persisted.
    """
    session = _owned_or_raise(db, account_id, session_id)
    now = _now()

    msg = models.SearchMessage(
        id=_new_id("msg"),
        session_id=session_id,
        account_id=account_id,
        role="user",
        content=message,
        created_at=now,
    )
    db.add(msg)
    db.flush()

    for rank, result in enumerate(results or []):
        image_id = (result or {}).get("image_id") or (result or {}).get("id")
        display_md = _safe_display_metadata(result)
        ref = models.SearchResultRef(
            id=_new_id("ref"),
            message_id=msg.id,
            session_id=session_id,
            account_id=account_id,
            image_id=image_id,
            rank=rank,
            display_metadata_json=json.dumps(display_md),
        )
        db.add(ref)

    # Persist active clues/context onto the conversation's SearchContext.
    _upsert_context(db, account_id, session_id, message=message, clues=clues)

    session.updated_at = now
    db.commit()
    return msg


def _upsert_context(
    db: Session,
    account_id: str,
    session_id: str,
    message: Optional[str] = None,
    clues: Optional[List[Dict[str, Any]]] = None,
) -> models.SearchContext:
    """Create/update the SearchContext row for a session (owner-scoped).

    Accumulates clue semantics as a JSON list on `content_clues`; keeps the
    original intent from the first turn and records the latest refinement as
    `updated_query`.
    """
    ctx = (
        db.query(models.SearchContext)
        .filter(models.SearchContext.session_id == session_id)
        .first()
    )
    clue_labels = [c.get("label") for c in (clues or []) if isinstance(c, dict) and c.get("label")]
    if ctx is None:
        ctx = models.SearchContext(
            session_id=session_id,
            account_id=account_id,
            original_intent=message,
            topic_clues=None,
            content_clues=json.dumps(clue_labels),
            visual_clues=None,
            metadata_filters=None,
            updated_query=message,
        )
        db.add(ctx)
    else:
        # Accumulate clues rather than discard prior context.
        existing: List[str] = []
        if ctx.content_clues:
            try:
                existing = json.loads(ctx.content_clues) or []
            except (ValueError, TypeError):
                existing = []
        merged = existing + [c for c in clue_labels if c not in existing]
        ctx.content_clues = json.dumps(merged)
        ctx.account_id = ctx.account_id or account_id
        ctx.updated_query = message
    return ctx


# ---------------------------------------------------------------------------
# 2.7 — list / get / delete / clear (account-scoped)
# ---------------------------------------------------------------------------

def list_conversations(db: Session, account_id: str) -> List[Dict[str, Any]]:
    """Return summaries (id/title/created_at/updated_at) of only owned sessions."""
    rows = (
        db.query(models.SearchSession)
        .filter(models.SearchSession.account_id == account_id)
        .order_by(models.SearchSession.updated_at.desc())
        .all()
    )
    return [
        {
            "sessionId": r.id,
            "title": r.title,
            "createdAt": _iso(r.created_at),
            "updatedAt": _iso(r.updated_at),
        }
        for r in rows
    ]


def get_conversation(db: Session, account_id: str, session_id: str) -> Dict[str, Any]:
    """Return the owned conversation: messages (ascending by created_at) with
    their result refs, plus persisted context. Raises 403/404 via _owned_or_raise.
    """
    session = _owned_or_raise(db, account_id, session_id)

    messages = (
        db.query(models.SearchMessage)
        .filter(models.SearchMessage.session_id == session_id)
        .order_by(models.SearchMessage.created_at.asc())
        .all()
    )

    message_dicts: List[Dict[str, Any]] = []
    for m in messages:
        refs = (
            db.query(models.SearchResultRef)
            .filter(models.SearchResultRef.message_id == m.id)
            .order_by(models.SearchResultRef.rank.asc())
            .all()
        )
        ref_dicts = []
        for ref in refs:
            try:
                display_md = json.loads(ref.display_metadata_json) if ref.display_metadata_json else {}
            except (ValueError, TypeError):
                display_md = {}
            ref_dicts.append(
                {
                    "imageId": ref.image_id,
                    "rank": ref.rank,
                    "displayMetadata": display_md,
                }
            )
        message_dicts.append(
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "createdAt": _iso(m.created_at),
                "results": ref_dicts,
            }
        )

    ctx_row = (
        db.query(models.SearchContext)
        .filter(models.SearchContext.session_id == session_id)
        .first()
    )
    context: Optional[Dict[str, Any]] = None
    if ctx_row is not None:
        context = {
            "originalIntent": ctx_row.original_intent,
            "topicClues": ctx_row.topic_clues,
            "contentClues": ctx_row.content_clues,
            "visualClues": ctx_row.visual_clues,
            "metadataFilters": ctx_row.metadata_filters,
            "updatedQuery": ctx_row.updated_query,
        }

    return {
        "sessionId": session.id,
        "title": session.title,
        "createdAt": _iso(session.created_at),
        "updatedAt": _iso(session.updated_at),
        "messages": message_dicts,
        "context": context,
    }


def rename_conversation(db: Session, account_id: str, session_id: str, title: Optional[str]) -> Dict[str, Any]:
    """Rename an owned conversation; return its updated summary."""
    session = _owned_or_raise(db, account_id, session_id)
    session.title = title
    session.updated_at = _now()
    db.commit()
    return {
        "sessionId": session.id,
        "title": session.title,
        "createdAt": _iso(session.created_at),
        "updatedAt": _iso(session.updated_at),
    }


def delete_conversation(db: Session, account_id: str, session_id: str) -> bool:
    """Delete only the owned conversation (and its messages/refs/context).

    Raises 403/404 via _owned_or_raise for cross-account/missing sessions.
    Leaves every other account's conversations unchanged.
    """
    _owned_or_raise(db, account_id, session_id)
    db.query(models.SearchResultRef).filter(
        models.SearchResultRef.session_id == session_id
    ).delete(synchronize_session=False)
    db.query(models.SearchMessage).filter(
        models.SearchMessage.session_id == session_id
    ).delete(synchronize_session=False)
    db.query(models.SearchContext).filter(
        models.SearchContext.session_id == session_id
    ).delete(synchronize_session=False)
    db.query(models.SearchSession).filter(
        models.SearchSession.id == session_id
    ).delete(synchronize_session=False)
    db.commit()
    return True


def clear_conversations(db: Session, account_id: str) -> int:
    """Delete ONLY the conversations owned by `account_id`. Returns the count of
    deleted sessions. There is intentionally no delete-all-accounts operation.
    """
    owned_ids = [
        r.id
        for r in db.query(models.SearchSession.id)
        .filter(models.SearchSession.account_id == account_id)
        .all()
    ]
    if not owned_ids:
        return 0
    db.query(models.SearchResultRef).filter(
        models.SearchResultRef.session_id.in_(owned_ids)
    ).delete(synchronize_session=False)
    db.query(models.SearchMessage).filter(
        models.SearchMessage.session_id.in_(owned_ids)
    ).delete(synchronize_session=False)
    db.query(models.SearchContext).filter(
        models.SearchContext.session_id.in_(owned_ids)
    ).delete(synchronize_session=False)
    db.query(models.SearchSession).filter(
        models.SearchSession.id.in_(owned_ids)
    ).delete(synchronize_session=False)
    db.commit()
    return len(owned_ids)
