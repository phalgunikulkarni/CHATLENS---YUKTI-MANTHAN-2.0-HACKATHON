"""P2S4 - Calendar + Task SERVICE-layer tests (stdlib harness; no pytest).

Real local integration: Taskwarrior CLI (per-account temp dir) + local calendar
store (temp dir). No network. If the `task` binary is unavailable, the
Taskwarrior tests self-skip (non-fatal). Run: python tests/test_calendar_tasks_service.py
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

# Route all storage to throwaway temp dirs BEFORE importing the services.
_TMP = tempfile.mkdtemp(prefix="ct-svc-")
os.environ["CHATLENS_CALENDAR_DIR"] = os.path.join(_TMP, "cal")
os.environ["CHATLENS_TASK_DIR"] = os.path.join(_TMP, "tasks")

from calendar_tasks.calendar_service import CalendarService
from calendar_tasks.task_service import TaskService, TaskServiceError
from calendar_tasks.validation import ValidationError

A, B = "acct-aaaa", "acct-bbbb"


def _task_available() -> bool:
    return shutil.which(os.environ.get("CHATLENS_TASK_BIN", "task")) is not None


# ---------------- Calendar (local store, always runs) ----------------
def test_calendar_create_and_get():
    cs = CalendarService()
    ev = cs.create_event(A, "Standup", "2026-09-10", "09:00", "09:15", "America/New_York", "team", None)
    assert ev.id and ev.created_at > 0
    got = cs.list_events(A)
    assert any(e.id == ev.id for e in got)


def test_calendar_timezone_preserved():
    cs = CalendarService()
    ev = cs.create_event(A, "TZ", "2026-09-11", "08:00", None, "Asia/Kolkata", "", None)
    fetched = [e for e in cs.list_events(A) if e.id == ev.id][0]
    assert fetched.timezone == "Asia/Kolkata"
    assert fetched.start_time == "08:00"  # local wall-clock unchanged


def test_calendar_account_isolation():
    cs = CalendarService()
    ev = cs.create_event(A, "Only A", "2026-09-12", "10:00", None, "UTC", "", None)
    b_ids = [e.id for e in cs.list_events(B)]
    assert ev.id not in b_ids


def test_calendar_validation_rejects():
    cs = CalendarService()
    for args in [("", "2026-09-12", "10:00"), ("x", "2026-13-40", "10:00"), ("x", "2026-09-12", "99:99")]:
        try:
            cs.create_event(A, args[0], args[1], args[2], None, "UTC", "", None)
            assert False, f"should reject {args}"
        except ValidationError:
            pass


def test_calendar_end_after_start():
    cs = CalendarService()
    try:
        cs.create_event(A, "x", "2026-09-12", "15:00", "14:00", "UTC", "", None)
        assert False, "should reject end<=start"
    except ValidationError:
        pass


def test_calendar_delete():
    cs = CalendarService()
    ev = cs.create_event(A, "temp", "2026-09-13", "10:00", None, "UTC", "", None)
    cs.delete_event(A, ev.id)
    assert all(e.id != ev.id for e in cs.list_events(A))
    try:
        cs.delete_event(A, ev.id)
        assert False, "deleting missing should raise"
    except ValidationError:
        pass


# ---------------- Tasks (real Taskwarrior; self-skip if missing) ----------------
def test_task_create_list_complete_delete_persistence_isolation():
    if not _task_available():
        print("  (skip task tests: task binary unavailable)")
        return
    ts = TaskService()
    t = ts.create_task(A, "Submit assignment", "2026-09-07", "17:00", "high")
    assert t.id and t.priority == "high" and t.due_date == "2026-09-07" and t.due_time == "17:00"
    # list
    assert any(x.id == t.id for x in ts.list_tasks(A))
    # complete + reopen (PATCH-equivalent)
    assert ts.update_task(A, t.id, {"completed": True}).completed is True
    assert ts.update_task(A, t.id, {"completed": False}).completed is False
    # supported field update
    up = ts.update_task(A, t.id, {"priority": "low", "title": "Submit report"})
    assert up.priority == "low" and up.title == "Submit report"
    # isolation
    assert all(x.id != t.id for x in ts.list_tasks(B))
    # persistence across a fresh service instance (real durable store)
    assert any(x.id == t.id for x in TaskService().list_tasks(A))
    # delete
    ts.delete_task(A, t.id)
    assert all(x.id != t.id for x in ts.list_tasks(A))


def test_task_validation_rejects():
    if not _task_available():
        print("  (skip task validation: task binary unavailable)")
        return
    ts = TaskService()
    try:
        ts.create_task(A, "", "2026-09-07", None, "high"); assert False
    except ValidationError:
        pass
    try:
        ts.create_task(A, "x", "2026-99-99", None, "high"); assert False
    except ValidationError:
        pass
    try:
        ts.create_task(A, "x", "2026-09-07", None, "urgent"); assert False
    except ValidationError:
        pass


def test_task_invalid_id_rejected():
    if not _task_available():
        print("  (skip: task binary unavailable)")
        return
    ts = TaskService()
    try:
        ts.update_task(A, "not a uuid ; rm -rf /", {"completed": True})
        assert False, "should reject bad id"
    except ValidationError:
        pass


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1; print(f"PASS {name}")
        except Exception:
            failed += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\ncalendar_tasks_service: {passed} passed, {failed} failed, {len(tests)} total")
    shutil.rmtree(_TMP, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
