"""Small, isolated reminder scheduling service (APScheduler-backed).

Keeps all scheduler logic out of the agent. In-memory BackgroundScheduler with a
process-lifetime job store (MVP). Persistence across restarts is intentionally
NOT wired to a new DB here (P2S2 scope note): APScheduler supports a SQLAlchemy
jobstore against the existing SQLite later if durable restart behavior is
required, but we do not introduce a second storage system now.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Reminder:
    id: str
    message: str
    run_at: str          # ISO 8601 string
    status: str = "scheduled"  # scheduled | fired | cancelled

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _fire(reminder_id: str, message: str) -> None:
    """Default job action: mark fired. Replaced by a real notifier later.
    Kept side-effect-light so tests/imports never block."""
    # Intentionally minimal for the MVP; a notification channel is future work.
    print(f"[reminder] fired {reminder_id}: {message}")


class ReminderService:
    """Thin wrapper over an APScheduler BackgroundScheduler.

    One shared scheduler per process. `fire_callback` is injectable so tests can
    observe firing without real timing.
    """

    _lock = threading.Lock()

    def __init__(self, fire_callback=None, autostart: bool = True) -> None:
        from apscheduler.schedulers.background import BackgroundScheduler

        self._scheduler = BackgroundScheduler()
        self._fire = fire_callback or _fire
        # image_id-independent registry of reminders we created.
        self._reminders: Dict[str, Reminder] = {}
        if autostart:
            self._scheduler.start()

    # -- operations -----------------------------------------------------------

    def create(self, message: str, run_at: datetime, reminder_id: Optional[str] = None) -> Reminder:
        if not message or not str(message).strip():
            raise ValueError("reminder message is required")
        if not isinstance(run_at, datetime):
            raise ValueError("run_at must be a datetime")
        rid = reminder_id or f"rem_{len(self._reminders)+1}_{int(run_at.timestamp())}"
        if rid in self._reminders and self._reminders[rid].status == "scheduled":
            raise ValueError(f"reminder id {rid} already scheduled")

        rem = Reminder(id=rid, message=str(message).strip(), run_at=run_at.isoformat())

        def _job(_rid=rid, _msg=rem.message):
            self._fire(_rid, _msg)
            r = self._reminders.get(_rid)
            if r is not None:
                r.status = "fired"

        # DateTrigger via run_date. Past times fire ~immediately (APScheduler).
        self._scheduler.add_job(_job, trigger="date", run_date=run_at, id=rid, replace_existing=False)
        self._reminders[rid] = rem
        return rem

    def list(self) -> List[Reminder]:
        # Reflect scheduler truth for still-scheduled jobs.
        live_ids = {j.id for j in self._scheduler.get_jobs()}
        for rid, rem in self._reminders.items():
            if rem.status == "scheduled" and rid not in live_ids:
                rem.status = "fired"
        return list(self._reminders.values())

    def cancel(self, reminder_id: str) -> Reminder:
        if not reminder_id or reminder_id not in self._reminders:
            raise ValueError(f"unknown reminder id {reminder_id!r}")
        try:
            self._scheduler.remove_job(reminder_id)
        except Exception:
            pass  # job may have already fired; still mark cancelled below
        rem = self._reminders[reminder_id]
        rem.status = "cancelled"
        return rem

    def shutdown(self) -> None:  # pragma: no cover - lifecycle helper
        try:
            self._scheduler.shutdown(wait=False)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Shared process-lifetime scheduler singleton.
#
# This is SHARED INFRASTRUCTURE (not a functional agent). Calendar event
# reminders use it via calendar_tasks/reminders.py. The functional Reminder
# agent was removed in the five-agent alignment; this accessor previously lived
# in reminder_agent.py and was moved here so the scheduler survives without the
# agent module.
# ---------------------------------------------------------------------------
_SHARED_SERVICE: Optional["ReminderService"] = None


def get_shared_service() -> "ReminderService":
    """Return the shared process-wide ReminderService (lazily created)."""
    global _SHARED_SERVICE
    if _SHARED_SERVICE is None:
        _SHARED_SERVICE = ReminderService()
    return _SHARED_SERVICE
