"""Clean reminder scheduling seam for Calendar + Tasks.

Reuses the EXISTING reminder infrastructure (agents.reminder_service) rather
than introducing a new scheduler. (The functional Reminder agent was removed in
the five-agent alignment; the scheduler service remains as shared infra.) Calendar events and tasks may OPTIONALLY
schedule an in-app reminder; nothing here converts a task into a calendar event.

This is a thin, best-effort seam: if scheduling is unavailable it degrades
quietly (the create/update still succeeds). P2S5/frontend can consume the
reminder callback later; no external/paid notification provider is used.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def schedule_in_app_reminder(reminder_id: str, message: str, run_at: datetime) -> bool:
    """Schedule a one-shot in-app reminder via the shared reminder service.

    Returns True if scheduled, False if the reminder infrastructure was not
    available. Never raises — reminders are a convenience, not a hard dependency.
    """
    try:
        from agents.reminder_service import get_shared_service  # shared scheduler infra
        svc = get_shared_service()
        svc.create(message=message, run_at=run_at, reminder_id=reminder_id)
        return True
    except Exception:  # noqa: BLE001 - best-effort; do not fail the parent op
        return False


def cancel_in_app_reminder(reminder_id: str) -> bool:
    try:
        from agents.reminder_service import get_shared_service
        get_shared_service().cancel(reminder_id)
        return True
    except Exception:  # noqa: BLE001
        return False
