"""Property test — search turn persistence round-trip (Task 2.10, Property 4).

Feature: account-scoped-chat-and-isolation.
Property 4: Search turn persistence round-trip.
Validates: Requirements R4.1, R4.2, R4.3, R4.4, R4.5.

For all accounts, owned sessions, and result sets of size 0..k, persisting a
search turn then reloading the conversation yields the same user query message
(with a creation timestamp) and exactly the same number of result references,
and none of the persisted references contain a filesystem path or binary field.
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
import chat_repo
from database import Base

_accounts = st.builds(lambda h: f"acct-{h}", st.text(alphabet="0123456789abcdef", min_size=1, max_size=8))

# A result row carries an image_id + path/binary fields that MUST be stripped.
_result = st.fixed_dictionaries(
    {
        "image_id": st.text(alphabet="0123456789abcdef", min_size=1, max_size=16),
        "filename": st.text(max_size=20),
        "category": st.text(max_size=10),
        "absolute_path": st.text(min_size=1, max_size=20),
        "file_path": st.text(min_size=1, max_size=20),
        "source_root": st.text(min_size=1, max_size=20),
        "score": st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
    }
)

_FORBIDDEN = {"path", "file_path", "absolute_path", "source_root", "binary", "stored_path", "thumbnailurl", "fullurl"}


def _fresh_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


@settings(max_examples=120, deadline=None)
@given(
    acct=_accounts,
    query=st.text(min_size=1, max_size=40),
    results=st.lists(_result, max_size=6),
)
def test_search_turn_round_trip(acct, query, results):
    db, engine = _fresh_session()
    try:
        sid = chat_repo.create_conversation(db, acct)
        chat_repo.append_search_turn(db, acct, sid, query, results)

        detail = chat_repo.get_conversation(db, acct, sid)
        # Exactly one user message with the same query and a creation timestamp.
        user_msgs = [m for m in detail["messages"] if m["role"] == "user"]
        assert len(user_msgs) == 1
        msg = user_msgs[0]
        assert msg["content"] == query
        assert msg["createdAt"] is not None
        # Exactly the same number of refs as results.
        assert len(msg["results"]) == len(results)

        # No ref carries a path/binary field.
        for ref in msg["results"]:
            md = ref["displayMetadata"] or {}
            for k in md.keys():
                lk = str(k).lower()
                assert lk not in _FORBIDDEN
                assert "path" not in lk

        # Storage layer: no path/binary column exists on SearchResultRef at all.
        raw_refs = db.query(models.SearchResultRef).filter_by(session_id=sid).all()
        for r in raw_refs:
            stored = json.loads(r.display_metadata_json) if r.display_metadata_json else {}
            for k in stored.keys():
                assert "path" not in str(k).lower()
    finally:
        db.close()
        engine.dispose()
