"""Smoke test for the Phase B harness (Task 2.1).

Verifies pytest discovers and runs with NO torch/CLIP/OCR import: the client
fixture fakes retrieval, and the fakes module is import-safe.
"""

import sys

import fakes


def test_no_heavy_ml_imported():
    # The harness must not pull torch/CLIP into the interpreter.
    assert "torch" not in sys.modules


def test_fake_chroma_honors_account_where():
    store = fakes.FakeChromaStore()
    store.upsert_visual("img1", {"image_id": "img1", "account_id": "acct-aaaa"})
    store.upsert_visual("img1", {"image_id": "img1", "account_id": "acct-bbbb"})
    a = store.query_visual(where={"account_id": "acct-aaaa"})
    b = store.query_visual(where={"account_id": "acct-bbbb"})
    assert len(a) == 1 and a[0]["metadata"]["account_id"] == "acct-aaaa"
    assert len(b) == 1 and b[0]["metadata"]["account_id"] == "acct-bbbb"
    # Account-qualified ids keep the same file's records distinct per account.
    assert store.get_visual_by_image_id("img1", "acct-aaaa") is not None
    assert store.get_visual_by_image_id("img1", "acct-bbbb") is not None


def test_client_fixture_boots_and_serves_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_temp_db_fixture(db_session):
    import models

    # A trivial write/read round-trip on the temp DB.
    s = models.SearchSession(id="session_x", account_id="acct-aaaa")
    db_session.add(s)
    db_session.commit()
    got = db_session.query(models.SearchSession).filter_by(id="session_x").first()
    assert got is not None and got.account_id == "acct-aaaa"
