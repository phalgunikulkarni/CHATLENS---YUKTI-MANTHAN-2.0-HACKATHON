"""Dataclasses mirroring the frontend CalendarEvent / TaskItem shapes.

Backend owns id + created_at. to_dict() produces exactly the JSON the frontend
expects. created_at is epoch milliseconds (matches the frontend number field).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class CalendarEvent:
    id: str
    title: str
    date: str                 # YYYY-MM-DD
    start_time: str           # HH:MM
    end_time: Optional[str]   # HH:MM or None
    timezone: str             # IANA
    participants: str         # free-form string
    reminder: Optional[str]   # string or None
    created_at: int           # epoch ms

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskItem:
    id: str
    title: str
    due_date: str             # YYYY-MM-DD
    due_time: Optional[str]   # HH:MM or None
    priority: str             # low | medium | high
    completed: bool
    created_at: int           # epoch ms

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
