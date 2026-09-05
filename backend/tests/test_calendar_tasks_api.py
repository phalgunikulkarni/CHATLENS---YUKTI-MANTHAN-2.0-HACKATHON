"""P2S4 - Calendar + Task HTTP endpoint tests (stdlib harness; no pytest).

Uses FastAPI TestClient against the real app with storage routed to temp dirs.
Verifies account scoping (X-Account-Id), validation, CRUD, and account
isolation over HTTP. No network required. Task endpoints self-skip if the
`task` binary is unavailable. Run: python tests/test_calendar_tasks_api.py
"""
from __future__ import annotations

import os
import sys
import shutil
import tempfile
import traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

_TMP = tempfile.mkdtemp(prefix="ct-api-")
os.environ["CHATLENS_CALENDAR_DIR"] = os.path.join(_TMP, "cal")
os.environ["CHATLENS_TASK_DIR"] = os.path.join(_TMP, "tasks")

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)
A = {"X-Account-Id": "acct-aaaa"}
B = {"X-Account-Id": "acct-bbbb"}


def _task_available() -> bool:
    return shutil.which(os.environ.get("CHATLENS_TASK_BIN", "task")) is not None


# ---------------- Calendar HTTP ----------------
def test_calendar_requires_account():
    assert client.get("/api/calendar/events").status_code == 401
    assert client.post("/api/calendar/events", json={}).status_code == 401


def test_calendar_get_empty_then_create_then_get():
    assert client.get("/api/calendar/events", headers=A).json() == []
    payload = {"title": "Demo", "date": "2026-09-20", "start_time": "12:00",
               "end_time": "13:00", "timezone": "Asia/Kolkata", "participants": "me", "reminder": "10 minutes"}
    r = client.post("/api/calendar/events", headers=A, json=payload)
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["id"] and ev["created_at"] > 0
    assert ev["timezone"] == "Asia/Kolkata" and ev["start_time"] == "12:00"
    got = client.get("/api/calendar/events", headers=A).json()
    assert any(e["id"] == ev["id"] for e in got)


def test_calendar_validation_400():
    bad = {"title": "", "date": "2026-13-99", "start_time": "99:99"}
    assert client.post("/api/calendar/events", headers=A, json=bad).status_code == 400


def test_calendar_account_isolation_http():
    payload = {"title": "A-only", "date": "2026-09-21", "start_time": "09:00", "timezone": "UTC"}
    ev = client.post("/api/calendar/events", headers=A, json=payload).json()
    b_events = client.get("/api/calendar/events", headers=B).json()
    assert all(e["id"] != ev["id"] for e in b_events)


def test_calendar_delete_http():
    payload = {"title": "delme", "date": "2026-09-22", "start_time": "09:00", "timezone": "UTC"}
    ev = client.post("/api/calendar/events", headers=A, json=payload).json()
    assert client.delete(f"/api/calendar/events/{ev['id']}", headers=A).status_code == 200
    assert client.delete(f"/api/calendar/events/{ev['id']}", headers=A).status_code == 404


# ---------------- Tasks HTTP ----------------
def test_tasks_requires_account():
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/tasks", json={}).status_code == 401


def test_tasks_full_crud_and_isolation():
    if not _task_available():
        print("  (skip task HTTP tests: task binary unavailable)")
        return
    assert client.get("/api/tasks", headers=A).status_code == 200
    r = client.post("/api/tasks", headers=A, json={"title": "Call dentist", "due_date": "2026-09-07", "due_time": "10:30", "priority": "medium"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["id"] and t["priority"] == "medium" and t["due_time"] == "10:30" and t["completed"] is False
    # PATCH completion
    p = client.patch(f"/api/tasks/{t['id']}", headers=A, json={"completed": True})
    assert p.status_code == 200 and p.json()["completed"] is True
    # PATCH supported fields
    p2 = client.patch(f"/api/tasks/{t['id']}", headers=A, json={"priority": "high", "title": "Call dentist urgently"})
    assert p2.json()["priority"] == "high" and p2.json()["title"] == "Call dentist urgently"
    # isolation
    assert all(x["id"] != t["id"] for x in client.get("/api/tasks", headers=B).json())
    # DELETE
    assert client.delete(f"/api/tasks/{t['id']}", headers=A).status_code == 200


def test_tasks_validation_400():
    if not _task_available():
        print("  (skip: task binary unavailable)")
        return
    assert client.post("/api/tasks", headers=A, json={"title": "", "due_date": "2026-09-07"}).status_code == 400
    assert client.post("/api/tasks", headers=A, json={"title": "x", "due_date": "bad", "priority": "medium"}).status_code == 400


def test_existing_routes_intact():
    assert client.get("/health").status_code == 200


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1; print(f"PASS {name}")
        except Exception:
            failed += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\ncalendar_tasks_api: {passed} passed, {failed} failed, {len(tests)} total")
    shutil.rmtree(_TMP, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
