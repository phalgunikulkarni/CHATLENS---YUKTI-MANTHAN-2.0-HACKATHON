"""Property test — single-owner conversations (Task 2.9, Property 3).

Feature: account-scoped-chat-and-isolation.
Property 3: Single-owner conversations.
Validates: Requirements R3.1, R3.3, R3.4, R3.5, R14.2.

For all accounts and conversations created by that account, the persisted
conversation records exactly one owning account_id equal to the resolving
account (never null/anonymous/previous/global), and creation does not modify any
pre-existing conversation.
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
import chat_repo
from database import Base

_accounts = st.builds(lambda h: f"acct-{h}", st.text(alphabet="0123456789abcdef", min_size=1, max_size=12))


def _fresh_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


@settings(max_examples=120, deadline=None)
@given(acct=_accounts, other=_accounts, title=st.one_of(st.none(), st.text(max_size=30)))
def test_created_conversation_has_single_resolved_owner(acct, other, title):
    db, engine = _fresh_session()
    try:
        # Pre-existing conversation owned by `other`.
        pre_id = chat_repo.create_conversation(db, other, title="pre")
        pre_before = db.query(models.SearchSession).filter_by(id=pre_id).first()
        pre_owner_before = pre_before.account_id
        pre_title_before = pre_before.title

        sid = chat_repo.create_conversation(db, acct, title=title)

        row = db.query(models.SearchSession).filter_by(id=sid).first()
        # Exactly one owner, equal to the resolving account; never null/global.
        assert row is not None
        assert row.account_id == acct
        assert row.account_id is not None

        # Pre-existing conversation is untouched by the new creation.
        pre_after = db.query(models.SearchSession).filter_by(id=pre_id).first()
        assert pre_after.account_id == pre_owner_before
        assert pre_after.title == pre_title_before
    finally:
        db.close()
        engine.dispose()
