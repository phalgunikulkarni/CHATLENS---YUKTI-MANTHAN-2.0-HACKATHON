"""Property test — refinement appends to same conversation (Task 2.11, Property 5).

Feature: account-scoped-chat-and-isolation.
Property 5: Refinement appends to the same owned conversation.
Validates: Requirements R5.1, R5.2, R5.3.

For all accounts and owned sessions, submitting a refinement appends a message
and its clues/context to that same conversation without creating a new one.
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
_clue = st.fixed_dictionaries({"id": st.text(min_size=1, max_size=6), "label": st.text(min_size=1, max_size=20)})


def _fresh_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


@settings(max_examples=120, deadline=None)
@given(
    acct=_accounts,
    initial=st.text(min_size=1, max_size=30),
    refinement=st.text(min_size=1, max_size=30),
    clues=st.lists(_clue, max_size=4),
)
def test_refinement_appends_same_conversation(acct, initial, refinement, clues):
    db, engine = _fresh_session()
    try:
        sid = chat_repo.create_conversation(db, acct)
        chat_repo.append_search_turn(db, acct, sid, initial, [])

        sessions_before = db.query(models.SearchSession).count()

        chat_repo.append_refine_turn(db, acct, sid, refinement, clues, [])

        # No new conversation created.
        assert db.query(models.SearchSession).count() == sessions_before

        detail = chat_repo.get_conversation(db, acct, sid)
        contents = [m["content"] for m in detail["messages"]]
        assert initial in contents
        assert refinement in contents
        # Same session id throughout.
        assert detail["sessionId"] == sid
        # Context persisted with the refinement's clues (labels accumulate).
        ctx = detail["context"]
        assert ctx is not None
        stored_clues = json.loads(ctx["contentClues"]) if ctx["contentClues"] else []
        for c in clues:
            assert c["label"] in stored_clues
    finally:
        db.close()
        engine.dispose()
