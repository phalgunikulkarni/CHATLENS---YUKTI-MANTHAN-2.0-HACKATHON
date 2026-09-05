"""P2S2 - Reminder Agent tests (stdlib harness; pytest not required).

Uses an injected ReminderService with a fake fire_callback and no autostart of
threads that would interfere, so tests are deterministic and fast. Run directly:
    python tests/test_reminder_agent.py
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

# Make backend/ importable (mirror conftest's Phase A behavior) without pytest.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from agents import AgentContext, AgentResult, AgentRegistry, Orchestrator, StaticRouter
from agents.reminder_agent import ReminderAgent
from agents.reminder_service import ReminderService


def _agent():
    fired = []
    svc = ReminderService(fire_callback=lambda rid, msg: fired.append((rid, msg)))
    return ReminderAgent(service=svc), svc, fired


def _future_iso(seconds=3600):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def test_create_reminder_structured_result():
    agent, _svc, _ = _agent()
    res = agent.run(AgentContext(params={
        "operation": "create", "message": "Pay rent", "run_at": _future_iso(),
    }))
    assert isinstance(res, AgentResult)
    assert res.ok, res.error
    rem = res.data["reminder"]
    assert rem["message"] == "Pay rent"
    assert rem["status"] == "scheduled"
    assert rem["id"]
    assert res.metadata["operation"] == "create"


def test_list_reminders():
    agent, _svc, _ = _agent()
    agent.run(AgentContext(params={"operation": "create", "message": "A", "run_at": _future_iso()}))
    agent.run(AgentContext(params={"operation": "create", "message": "B", "run_at": _future_iso()}))
    res = agent.run(AgentContext(params={"operation": "list"}))
    assert res.ok
    ids = [r["id"] for r in res.data["reminders"]]
    assert len(ids) == 2 and len(set(ids)) == 2


def test_cancel_reminder():
    agent, _svc, _ = _agent()
    c = agent.run(AgentContext(params={"operation": "create", "message": "C", "run_at": _future_iso()}))
    rid = c.data["reminder"]["id"]
    res = agent.run(AgentContext(params={"operation": "cancel", "reminder_id": rid}))
    assert res.ok
    assert res.data["reminder"]["status"] == "cancelled"


def test_cancel_unknown_is_controlled_failure():
    agent, _svc, _ = _agent()
    res = agent.run(AgentContext(params={"operation": "cancel", "reminder_id": "nope"}))
    assert not res.ok
    assert res.error and "unknown reminder id" in res.error


def test_invalid_operation_is_failure():
    agent, _svc, _ = _agent()
    res = agent.run(AgentContext(params={"operation": "frobnicate"}))
    assert not res.ok and "unknown operation" in res.error


def test_create_missing_message_is_failure():
    agent, _svc, _ = _agent()
    res = agent.run(AgentContext(params={"operation": "create", "run_at": _future_iso()}))
    assert not res.ok and res.error


def test_create_invalid_run_at_is_failure():
    agent, _svc, _ = _agent()
    res = agent.run(AgentContext(params={"operation": "create", "message": "X", "run_at": "not-a-date"}))
    assert not res.ok and "invalid run_at" in res.error


def test_run_at_accepts_epoch_and_Z():
    agent, _svc, _ = _agent()
    epoch = (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()
    r1 = agent.run(AgentContext(params={"operation": "create", "message": "epoch", "run_at": epoch}))
    r2 = agent.run(AgentContext(params={"operation": "create", "message": "z",
                                        "run_at": "2999-01-01T00:00:00Z"}))
    assert r1.ok and r2.ok


def test_dispatch_through_orchestrator():
    agent, _svc, _ = _agent()
    reg = AgentRegistry(); reg.register(agent)
    orch = Orchestrator(reg, StaticRouter())
    res = orch.dispatch(AgentContext(params={"operation": "list", "agent": "reminder"}),
                        agent_id="reminder")
    assert res.ok and res.agent == "reminder"


def test_bad_input_never_raises_through_orchestrator():
    agent, _svc, _ = _agent()
    reg = AgentRegistry(); reg.register(agent)
    orch = Orchestrator(reg)
    # None params-ish and garbage should still yield a controlled failure.
    res = orch.dispatch(AgentContext(params={"operation": None}), agent_id="reminder")
    assert isinstance(res, AgentResult) and not res.ok


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\nreminder_agent: {passed} passed, {failed} failed, {len(tests)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
