"""FastAPI routes for ChatLens-owned Calendar + Tasks (P2S4).

Mounted onto the existing app in main.py via `register_calendar_tasks_routes(app)`.
Every endpoint is account-scoped via the existing `resolve_account` dependency
(the frontend's X-Account-Id). No second auth system; a client-supplied account
id is never trusted as authority. Responses/errors follow the project's
conventions (structured JSON, HTTPException with safe messages).

Frontend field names are snake_case (matching the existing frontend contract).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from account import resolve_account
from .calendar_service import CalendarService, CalendarServiceError
from .task_service import TaskService, TaskServiceError
from .validation import ValidationError

# Shared service singletons (stateless; store handles per-account isolation).
_calendar = CalendarService()
_tasks = TaskService()


# ---- Pydantic request models (creation payloads omit id/created_at) --------
class CalendarEventCreate(BaseModel):
    title: str
    date: str
    start_time: str
    end_time: Optional[str] = None
    timezone: Optional[str] = None
    participants: Optional[str] = ""
    reminder: Optional[str] = None


class CalendarEventOut(BaseModel):
    id: str
    title: str
    date: str
    start_time: str
    end_time: Optional[str]
    timezone: str
    participants: str
    reminder: Optional[str]
    created_at: int


class TaskCreate(BaseModel):
    title: str
    due_date: str
    due_time: Optional[str] = None
    priority: str = "medium"
    completed: bool = False


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None


class TaskOut(BaseModel):
    id: str
    title: str
    due_date: str
    due_time: Optional[str]
    priority: str
    completed: bool
    created_at: int


def register_calendar_tasks_routes(app: FastAPI) -> None:
    # ---------------- Calendar ----------------
    @app.get("/api/calendar/events", response_model=List[CalendarEventOut])
    def list_calendar_events(account: str = Depends(resolve_account)):
        try:
            return [e.to_dict() for e in _calendar.list_events(account)]
        except CalendarServiceError:
            raise HTTPException(status_code=500, detail="Calendar is temporarily unavailable")

    @app.post("/api/calendar/events", response_model=CalendarEventOut, status_code=201)
    def create_calendar_event(body: CalendarEventCreate, account: str = Depends(resolve_account)):
        try:
            ev = _calendar.create_event(
                account_id=account,
                title=body.title,
                date=body.date,
                start_time=body.start_time,
                end_time=body.end_time,
                timezone=body.timezone,
                participants=body.participants,
                reminder=body.reminder,
            )
            return ev.to_dict()
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except CalendarServiceError:
            raise HTTPException(status_code=500, detail="Could not create the event")

    @app.delete("/api/calendar/events/{event_id}")
    def delete_calendar_event(event_id: str, account: str = Depends(resolve_account)):
        try:
            _calendar.delete_event(account, event_id)
            return {"deleted": event_id}
        except ValidationError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except CalendarServiceError:
            raise HTTPException(status_code=500, detail="Could not delete the event")

    # ---------------- Tasks ----------------
    @app.get("/api/tasks", response_model=List[TaskOut])
    def list_tasks(account: str = Depends(resolve_account)):
        try:
            return [t.to_dict() for t in _tasks.list_tasks(account)]
        except TaskServiceError:
            raise HTTPException(status_code=500, detail="Tasks are temporarily unavailable")

    @app.post("/api/tasks", response_model=TaskOut, status_code=201)
    def create_task(body: TaskCreate, account: str = Depends(resolve_account)):
        try:
            t = _tasks.create_task(
                account_id=account,
                title=body.title,
                due_date=body.due_date,
                due_time=body.due_time,
                priority=body.priority,
                completed=body.completed,
            )
            return t.to_dict()
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except TaskServiceError:
            raise HTTPException(status_code=500, detail="Could not create the task")

    @app.patch("/api/tasks/{task_id}", response_model=TaskOut)
    def update_task(task_id: str, body: TaskUpdate, account: str = Depends(resolve_account)):
        patch = {k: v for k, v in body.model_dump().items() if v is not None or k == "completed"}
        # Only include completed if explicitly provided.
        if body.completed is None:
            patch.pop("completed", None)
        try:
            t = _tasks.update_task(account, task_id, patch)
            return t.to_dict()
        except ValidationError as exc:
            raise HTTPException(status_code=404 if "not found" in str(exc) else 400, detail=str(exc))
        except TaskServiceError:
            raise HTTPException(status_code=500, detail="Could not update the task")

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: str, account: str = Depends(resolve_account)):
        try:
            _tasks.delete_task(account, task_id)
            return {"deleted": task_id}
        except ValidationError as exc:
            raise HTTPException(status_code=404 if "not found" in str(exc) else 400, detail=str(exc))
        except TaskServiceError:
            raise HTTPException(status_code=500, detail="Could not delete the task")
