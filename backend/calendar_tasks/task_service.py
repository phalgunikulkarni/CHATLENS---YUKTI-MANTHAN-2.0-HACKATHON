"""Task service backed by the Taskwarrior CLI (per-account, durable).

- Persistence: Taskwarrior's own SQLite store, one data directory PER ACCOUNT
  (account isolation). Never an in-memory list.
- The frontend never invokes Taskwarrior. Frontend fields (due_date, due_time,
  priority, completed, created_at) are stored LOSSLESSLY via Taskwarrior UDAs +
  status, so no timezone reinterpretation occurs.
- Safe subprocess: argument arrays only, never shell=True, no user input in a
  shell string, validated UUIDs, clean failure handling.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional

from . import config
from .models import TaskItem
from .validation import (
    ValidationError,
    valid_date,
    valid_priority,
    optional_time,
    require_nonempty,
)

_UUID_RE = re.compile(r"^[0-9a-fA-F-]{8,36}$")
_ACCOUNT_RE = re.compile(r"^acct-[0-9a-f]+$")

# Priority mapping frontend <-> Taskwarrior (H/M/L).
_PRIO_TO_TW = {"low": "L", "medium": "M", "high": "H"}
_TW_TO_PRIO = {"L": "low", "M": "medium", "H": "high", "": "medium"}

# UDA definitions passed on EVERY invocation so the store stays consistent
# without writing a global taskrc (keeps account dirs self-contained).
_UDA_RC = [
    "rc.uda.duedate.type=string", "rc.uda.duedate.label=DueDate",
    "rc.uda.duetime.type=string", "rc.uda.duetime.label=DueTime",
    "rc.uda.tz.type=string", "rc.uda.tz.label=Timezone",
    "rc.uda.createdms.type=string", "rc.uda.createdms.label=CreatedMs",
]
_BASE_RC = ["rc.confirmation=off", "rc.verbose=nothing", "rc.recurrence=off", "rc.hooks=off"]


class TaskServiceError(Exception):
    """Task backend failure (-> HTTP 500 with a safe message)."""


def _account_dir(account_id: str) -> str:
    if not account_id or not _ACCOUNT_RE.match(account_id):
        # Defense-in-depth: routes already validate via resolve_account.
        raise TaskServiceError("invalid account")
    d = os.path.join(config.task_data_root(), account_id)
    os.makedirs(d, exist_ok=True)
    # Taskwarrior 3.x refuses to run when TASKRC points at a missing file
    # ("Cannot proceed without rc file"). Ensure a per-account (empty) rc file
    # exists so each account's config/data stays fully isolated and no shared
    # ~/.taskrc is used.
    rc = os.path.join(d, ".taskrc")
    if not os.path.exists(rc):
        try:
            open(rc, "a").close()
        except OSError as exc:
            raise TaskServiceError("could not initialize task store") from exc
    return d


def _run(account_id: str, args: List[str], expect_json: bool = False) -> Any:
    """Run a taskwarrior command for one account. argv only; never shell=True."""
    env = dict(os.environ)
    env["TASKDATA"] = _account_dir(account_id)
    env["TASKRC"] = os.path.join(_account_dir(account_id), ".taskrc")  # per-account, may not exist
    cmd = [config.task_binary(), *_BASE_RC, *_UDA_RC, *args]
    try:
        proc = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=20, check=False,
        )
    except FileNotFoundError as exc:
        raise TaskServiceError("task engine is not available") from exc
    except subprocess.TimeoutExpired as exc:
        raise TaskServiceError("task engine timed out") from exc
    if proc.returncode not in (0,):
        # Taskwarrior uses non-zero for "no matches" on some verbs; treat export
        # specially (empty result), otherwise surface a safe error.
        if expect_json and (proc.stdout.strip() in ("", "[]")):
            return []
        raise TaskServiceError("task engine command failed")
    if expect_json:
        out = proc.stdout.strip()
        if not out:
            return []
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            raise TaskServiceError("task engine returned malformed data") from exc
    return proc.stdout


def _to_task_item(row: Dict[str, Any]) -> TaskItem:
    created_ms = row.get("createdms")
    try:
        created_at = int(created_ms) if created_ms else int(time.time() * 1000)
    except (TypeError, ValueError):
        created_at = int(time.time() * 1000)
    return TaskItem(
        id=row.get("uuid", ""),
        title=row.get("description", ""),
        due_date=row.get("duedate", "") or "",
        due_time=row.get("duetime") or None,
        priority=_TW_TO_PRIO.get(row.get("priority", ""), "medium"),
        completed=row.get("status") == "completed",
        created_at=created_at,
    )


class TaskService:
    """Account-scoped task operations over Taskwarrior."""

    def list_tasks(self, account_id: str) -> List[TaskItem]:
        rows = _run(account_id, ["export"], expect_json=True)
        # Exclude deleted; include pending + completed.
        items = [_to_task_item(r) for r in rows if r.get("status") in ("pending", "completed")]
        return items

    def create_task(
        self,
        account_id: str,
        title: str,
        due_date: str,
        due_time: Optional[str],
        priority: str,
        completed: bool = False,
    ) -> TaskItem:
        title = require_nonempty(title, "title")
        due_date = valid_date(due_date, "due_date")
        due_time = optional_time(due_time, "due_time")
        priority = valid_priority(priority)
        created_ms = str(int(time.time() * 1000))

        # description must be a single argv element; no shell involved.
        args = [
            "add", title,
            f"priority:{_PRIO_TO_TW[priority]}",
            f"duedate:{due_date}",
            f"createdms:{created_ms}",
        ]
        if due_time:
            args.append(f"duetime:{due_time}")
        out = _run(account_id, args)
        # Parse the created uuid back out (add prints "Created task N."); fetch by
        # the createdms UDA to get the uuid reliably.
        rows = _run(account_id, [f"createdms:{created_ms}", "export"], expect_json=True)
        if not rows:
            raise TaskServiceError("task creation could not be confirmed")
        item = _to_task_item(rows[0])
        if completed:
            item = self.update_task(account_id, item.id, {"completed": True})
        return item

    def _resolve_uuid(self, account_id: str, task_id: str) -> str:
        if not task_id or not _UUID_RE.match(task_id):
            raise ValidationError("invalid task id")
        rows = _run(account_id, [task_id, "export"], expect_json=True)
        rows = [r for r in rows if r.get("uuid") == task_id]
        if not rows:
            raise ValidationError("task not found")
        return task_id

    def update_task(self, account_id: str, task_id: str, patch: Dict[str, Any]) -> TaskItem:
        uuid = self._resolve_uuid(account_id, task_id)

        # completion toggle
        if "completed" in patch:
            if patch["completed"]:
                _run(account_id, [uuid, "done"])
            else:
                _run(account_id, [uuid, "modify", "status:pending"])

        mods: List[str] = []
        if "title" in patch and patch["title"] is not None:
            mods.append(require_nonempty(patch["title"], "title"))
        if "priority" in patch and patch["priority"] is not None:
            mods.append(f"priority:{_PRIO_TO_TW[valid_priority(patch['priority'])]}")
        if "due_date" in patch and patch["due_date"] is not None:
            mods.append(f"duedate:{valid_date(patch['due_date'], 'due_date')}")
        if "due_time" in patch:
            t = optional_time(patch.get("due_time"), "due_time")
            mods.append(f"duetime:{t or ''}")
        if mods:
            _run(account_id, [uuid, "modify", *mods])

        rows = _run(account_id, [uuid, "export"], expect_json=True)
        rows = [r for r in rows if r.get("uuid") == uuid]
        if not rows:
            raise TaskServiceError("task update could not be confirmed")
        return _to_task_item(rows[0])

    def delete_task(self, account_id: str, task_id: str) -> None:
        uuid = self._resolve_uuid(account_id, task_id)
        _run(account_id, [uuid, "delete"])
