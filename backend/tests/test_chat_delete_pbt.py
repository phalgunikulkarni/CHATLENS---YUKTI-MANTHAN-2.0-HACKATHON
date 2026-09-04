"""Property test — owned-only deletion (Task 2.13, Property 8).

Feature: account-scoped-chat-and-isolation.
Property 8: Owned-only deletion.
Validates: Requirements R8.1, R8.3, R14.4.

For all pairs of distinct accounts A and B, deleting or clearing A's
conversations removes only conversations owned by A and leaves every
conversation owned by B unchanged.
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
import chat_repo
from database import Base


def _fresh_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


@settings(max_examples=120, deadline=None)
@given(
    n_a=st.integers(min_value=1, max_value=6),
    n_b=st.integers(min_value=1, max_value=6),
)
def test_delete_and_clear_only_touch_owner(n_a, n_b):
    db, engine = _fresh_session()
    a, b = "acct-aaaa", "acct-bbbb"
    try:
        a_ids = [chat_repo.create_conversation(db, a) for _ in range(n_a)]
        b_ids = [chat_repo.create_conversation(db, b) for _ in range(n_b)]

        # Delete one of A's conversations: B's set is unchanged.
        chat_repo.delete_conversation(db, a, a_ids[0])
        remaining_b = {s["sessionId"] for s in chat_repo.list_conversations(db, b)}
        assert remaining_b == set(b_ids)

        # Clear all of A's conversations: only A's rows removed.
        chat_repo.clear_conversations(db, a)
        assert chat_repo.list_conversations(db, a) == []
        assert {s["sessionId"] for s in chat_repo.list_conversations(db, b)} == set(b_ids)

        # B's rows physically remain in the tables.
        assert db.query(models.SearchSession).filter_by(account_id=a).count() == 0
        assert db.query(models.SearchSession).filter_by(account_id=b).count() == n_b
    finally:
        db.close()
        engine.dispose()
