"""Property test — chat list/order account-scoped (Task 2.12, Property 6).

Feature: account-scoped-chat-and-isolation.
Property 6: Chat list and ordering are account-scoped.
Validates: Requirements R6.1, R6.2.

For all sets of conversations across multiple accounts, an account's chat list
returns exactly the conversations it owns, and opening an owned session returns
its messages in ascending creation-time order together with its references and
context.
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import chat_repo
from database import Base

_accounts = st.sampled_from(["acct-aaaa", "acct-bbbb", "acct-cccc"])


def _fresh_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


@settings(max_examples=120, deadline=None)
@given(owners=st.lists(_accounts, min_size=1, max_size=12))
def test_list_returns_only_owned(owners):
    db, engine = _fresh_session()
    try:
        created = {}  # account -> set of session ids
        for owner in owners:
            sid = chat_repo.create_conversation(db, owner)
            created.setdefault(owner, set()).add(sid)

        for acct in set(owners):
            listed = chat_repo.list_conversations(db, acct)
            listed_ids = {s["sessionId"] for s in listed}
            assert listed_ids == created[acct]
            # No conversation from another account appears.
            for other, ids in created.items():
                if other == acct:
                    continue
                assert listed_ids.isdisjoint(ids)
    finally:
        db.close()
        engine.dispose()


@settings(max_examples=60, deadline=None)
@given(acct=_accounts, queries=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5))
def test_get_returns_messages_in_ascending_order(acct, queries):
    db, engine = _fresh_session()
    try:
        sid = chat_repo.create_conversation(db, acct)
        for q in queries:
            chat_repo.append_search_turn(db, acct, sid, q, [])
        detail = chat_repo.get_conversation(db, acct, sid)
        times = [m["createdAt"] for m in detail["messages"]]
        assert times == sorted(times)
        assert len(detail["messages"]) == len(queries)
    finally:
        db.close()
        engine.dispose()
