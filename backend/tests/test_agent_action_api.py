"""P2S5 - agent-action endpoint + add_calendar/add_task agents (stdlib harness).

Verifies: confirmation-before-mutation over HTTP, allowlist, account isolation,
validation, and that confirmed actions create via the real services. No network.
Task-backed cases self-skip if the `task` binary is unavailable.
Run: python tests/test_agent_action_api.py
"""
from __future__ import annotations

import os, sys, shutil, tempfile, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
_TMP = tempfile.mkdtemp(prefix="p2s5-")
os.environ["CHATLENS_CALENDAR_DIR"] = os.path.join(_TMP, "cal")
os.environ["CHATLENS_TASK_DIR"] = os.path.join(_TMP, "tasks")

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)
A = {"X-Account-Id": "acct-aaaa"}
B = {"X-Account-Id": "acct-bbbb"}


def _task_ok():
    return shutil.which(os.environ.get("CHATLENS_TASK_BIN", "task")) is not None


def test_action_requires_account():
    r = client.post("/api/agents/action", json={"agent": "add_calendar", "confirmed": True, "params": {}})
    assert r.status_code == 401


def test_action_rejects_unknown_agent():
    r = client.post("/api/agents/action", headers=A, json={"agent": "research", "confirmed": True, "params": {}})
    assert r.status_code == 400
    r2 = client.post("/api/agents/action", headers=A, json={"agent": "rm_rf", "confirmed": True, "params": {}})
    assert r2.status_code == 400


def test_add_calendar_unconfirmed_does_not_mutate():
    before = client.get("/api/calendar/events", headers=A).json()
    r = client.post("/api/agents/action", headers=A, json={
        "agent": "add_calendar", "confirmed": False,
        "params": {"title": "Meeting", "date": "2026-09-15", "start_time": "16:00"},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["data"]["confirmed"] is False
    after = client.get("/api/calendar/events", headers=A).json()
    assert len(after) == len(before)  # nothing created


def test_add_calendar_confirmed_creates_and_isolated():
    r = client.post("/api/agents/action", headers=A, json={
        "agent": "add_calendar", "confirmed": True,
        "params": {"title": "Meeting w Rahul", "date": "2026-09-15", "start_time": "16:00",
                   "timezone": "Asia/Kolkata", "participants": "Rahul", "reminder": "10 minutes"},
    })
    assert r.status_code == 200, r.text
    ev = r.json()["data"]["event"]
    assert ev["id"] and ev["timezone"] == "Asia/Kolkata" and ev["start_time"] == "16:00"
    # appears on the calendar for A
    a_events = client.get("/api/calendar/events", headers=A).json()
    assert any(e["id"] == ev["id"] for e in a_events)
    # isolated from B
    b_events = client.get("/api/calendar/events", headers=B).json()
    assert all(e["id"] != ev["id"] for e in b_events)


def test_add_calendar_validation_400():
    r = client.post("/api/agents/action", headers=A, json={
        "agent": "add_calendar", "confirmed": True,
        "params": {"title": "", "date": "2026-13-99", "start_time": "99:99"},
    })
    assert r.status_code == 400


def test_add_task_flow():
    if not _task_ok():
        print("  (skip add_task HTTP: task binary unavailable)")
        return
    # unconfirmed preview -> no task
    before = client.get("/api/tasks", headers=A).json()
    client.post("/api/agents/action", headers=A, json={
        "agent": "add_task", "confirmed": False,
        "params": {"title": "Submit assignment", "due_date": "2026-09-16"},
    })
    assert len(client.get("/api/tasks", headers=A).json()) == len(before)
    # confirmed -> creates
    r = client.post("/api/agents/action", headers=A, json={
        "agent": "add_task", "confirmed": True,
        "params": {"title": "Submit assignment", "due_date": "2026-09-16", "due_time": "17:00", "priority": "high"},
    })
    assert r.status_code == 200, r.text
    t = r.json()["data"]["task"]
    assert t["priority"] == "high" and t["due_time"] == "17:00" and t["completed"] is False
    assert any(x["id"] == t["id"] for x in client.get("/api/tasks", headers=A).json())
    assert all(x["id"] != t["id"] for x in client.get("/api/tasks", headers=B).json())


def test_existing_routes_intact():
    assert client.get("/health").status_code == 200


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try:
            fn(); p += 1; print(f"PASS {name}")
        except Exception:
            f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nagent_action_api: {p} passed, {f} failed, {len(tests)} total")
    shutil.rmtree(_TMP, ignore_errors=True)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
