"""P2S5 - add_calendar / add_task agent unit tests (mocked services; fast).

No Taskwarrior/CalDAV needed: services are injected fakes. Verifies confirmation
gating, validation pass-through, account requirement, and structured results.
Run: python tests/test_add_calendar_task_agents.py
"""
from __future__ import annotations

import os, sys, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from agents import AgentContext, AgentResult
from agents.add_calendar_agent import AddCalendarAgent
from agents.add_task_agent import AddTaskAgent
from calendar_tasks.models import CalendarEvent, TaskItem
from calendar_tasks.validation import ValidationError


class FakeCalendar:
    def __init__(self): self.created = []
    def create_event(self, account_id, title, date, start_time, end_time, timezone, participants, reminder):
        if not title: raise ValidationError("title is required")
        ev = CalendarEvent(id="evt-1", title=title, date=date, start_time=start_time,
                           end_time=end_time, timezone=timezone or "UTC",
                           participants=participants or "", reminder=reminder, created_at=123)
        self.created.append((account_id, ev)); return ev


class FakeTasks:
    def __init__(self): self.created = []
    def create_task(self, account_id, title, due_date, due_time, priority, completed=False):
        if not title: raise ValidationError("title is required")
        t = TaskItem(id="task-1", title=title, due_date=due_date, due_time=due_time,
                     priority=priority, completed=completed, created_at=123)
        self.created.append((account_id, t)); return t


def test_calendar_requires_confirmation():
    fc = FakeCalendar(); a = AddCalendarAgent(service=fc)
    r = a.run(AgentContext(account_id="acct-a", params={"title":"x","date":"2026-09-15","start_time":"10:00"}))
    assert isinstance(r, AgentResult) and r.ok and r.data["confirmed"] is False
    assert fc.created == []  # NOT created


def test_calendar_confirmed_creates():
    fc = FakeCalendar(); a = AddCalendarAgent(service=fc)
    r = a.run(AgentContext(account_id="acct-a", params={"confirmed":True,"title":"x","date":"2026-09-15","start_time":"10:00","timezone":"Asia/Kolkata"}))
    assert r.ok and r.data["event"]["timezone"] == "Asia/Kolkata"
    assert len(fc.created) == 1 and fc.created[0][0] == "acct-a"


def test_calendar_requires_account():
    a = AddCalendarAgent(service=FakeCalendar())
    r = a.run(AgentContext(params={"confirmed":True,"title":"x","date":"2026-09-15","start_time":"10:00"}))
    assert not r.ok and r.error == "no_account"


def test_calendar_validation_failure():
    a = AddCalendarAgent(service=FakeCalendar())
    r = a.run(AgentContext(account_id="acct-a", params={"confirmed":True,"title":"","date":"2026-09-15","start_time":"10:00"}))
    assert not r.ok and r.error.startswith("validation")


def test_task_requires_confirmation():
    ft = FakeTasks(); a = AddTaskAgent(service=ft)
    r = a.run(AgentContext(account_id="acct-a", params={"title":"x","due_date":"2026-09-16"}))
    assert r.ok and r.data["confirmed"] is False and ft.created == []


def test_task_confirmed_creates():
    ft = FakeTasks(); a = AddTaskAgent(service=ft)
    r = a.run(AgentContext(account_id="acct-a", params={"confirmed":True,"title":"x","due_date":"2026-09-16","priority":"high"}))
    assert r.ok and r.data["task"]["priority"] == "high"
    assert len(ft.created) == 1 and ft.created[0][0] == "acct-a"


def test_task_requires_account():
    a = AddTaskAgent(service=FakeTasks())
    r = a.run(AgentContext(params={"confirmed":True,"title":"x","due_date":"2026-09-16"}))
    assert not r.ok and r.error == "no_account"


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try: fn(); p += 1; print(f"PASS {name}")
        except Exception: f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nadd_calendar_task_agents: {p} passed, {f} failed, {len(tests)} total")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
