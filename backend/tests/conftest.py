"""Minimal pytest setup for the account-scoped-chat-and-isolation Phase A tests.

This is intentionally tiny: it only puts the `backend/` package directory on
`sys.path` so `import account`, `import main`, etc. resolve the same way they do
when the app runs (the app is launched from within `backend/`). The full Phase B
harness/fakes are out of scope for Phase A.

`backend/main` is import-safe: `ml_retrieval` lazily loads the retriever and
`access_service` lazily loads the indexer, so importing the app for a FastAPI
TestClient does NOT import torch/CLIP/OCR.
"""

import os
import sys

# Ensure the backend package root (parent of this tests/ dir) is importable.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Also make the tests dir importable so `import fakes` (Phase B harness) works.
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)


# ---------------------------------------------------------------------------
# Phase B harness: temp SQLite DB + TestClient fixtures + ml/ fakes.
#
# These EXTEND the minimal Phase A setup above without altering it. Phase A
# tests import `main`/`account` directly and do not use these fixtures, so they
# are unaffected.
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


@pytest.fixture
def db_session(tmp_path):
    """A SQLAlchemy Session bound to a fresh temp SQLite file DB.

    Creates all tables (including the new search_result_refs table and the
    additive account_id/title columns) on a throwaway engine so no real
    chatlens.db data is touched.
    """
    import models  # noqa: F401 - ensure models are registered on Base
    from database import Base

    db_url = f"sqlite:///{tmp_path / 'test_chat.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient backed by a temp SQLite DB, with retrieval faked.

    - Overrides `main.get_db` to use a temp DB engine (no real chatlens.db).
    - Monkeypatches `ml_retrieval.search_memories` to a deterministic list so no
      torch/CLIP/OCR loads; this exercises PERSISTENCE, not retrieval.
    The fake return value can be set per-test via `client.set_search_results(...)`.
    """
    import main
    from database import Base

    db_url = f"sqlite:///{tmp_path / 'client_chat.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[main.get_db] = _override_get_db

    # Deterministic, mutable search result holder (default: empty).
    holder = {"rows": []}

    def _fake_search_memories(query, top_k=5):
        if not query or not query.strip():
            return []
        return list(holder["rows"])[:top_k]

    monkeypatch.setattr(main.ml_retrieval, "search_memories", _fake_search_memories)

    from fastapi.testclient import TestClient

    test_client = TestClient(main.app)

    def _set_search_results(rows):
        holder["rows"] = rows

    # Attach a helper so tests can configure the fake retrieval output.
    test_client.set_search_results = _set_search_results  # type: ignore[attr-defined]

    try:
        yield test_client
    finally:
        main.app.dependency_overrides.pop(main.get_db, None)
        engine.dispose()
