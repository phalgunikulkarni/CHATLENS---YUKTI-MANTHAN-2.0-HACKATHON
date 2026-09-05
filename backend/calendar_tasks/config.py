"""Environment-driven configuration for Calendar + Tasks.

No secrets are hard-coded. CalDAV credentials come ONLY from the environment;
when unset, the CalendarService uses a durable LOCAL store so the API works in
development without a running Radicale server. Data directories default under a
git-ignored backend/storage/ location (already used by the project).
"""
from __future__ import annotations

import os

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__ + "/.."))
_STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "storage")


def _abspath(*parts: str) -> str:
    return os.path.abspath(os.path.join(_STORAGE_DIR, *parts))


# ---- CalDAV / Radicale (calendar engine) ----------------------------------
# When CHATLENS_CALDAV_URL is set, the CalendarService talks to that CalDAV
# server (e.g. a locally-hosted Radicale). Otherwise it uses the local store.
CALDAV_URL = os.getenv("CHATLENS_CALDAV_URL", "").strip()
CALDAV_USERNAME = os.getenv("CHATLENS_CALDAV_USERNAME", "").strip()
CALDAV_PASSWORD = os.getenv("CHATLENS_CALDAV_PASSWORD", "")  # never logged/echoed


def caldav_configured() -> bool:
    return bool(CALDAV_URL)


# ---- Local durable stores (fallback / default) ----------------------------
# Calendar events as per-account .ics-style JSON collections; tasks via
# Taskwarrior per-account data dirs. Overridable for tests.
def calendar_data_dir() -> str:
    return os.getenv("CHATLENS_CALENDAR_DIR", _abspath("calendar"))


def task_data_root() -> str:
    """Root under which each account gets its own Taskwarrior data directory."""
    return os.getenv("CHATLENS_TASK_DIR", _abspath("tasks"))


# ---- Taskwarrior binary ---------------------------------------------------
def task_binary() -> str:
    return os.getenv("CHATLENS_TASK_BIN", "task")
