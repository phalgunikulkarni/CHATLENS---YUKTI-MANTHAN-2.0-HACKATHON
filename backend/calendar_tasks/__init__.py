"""ChatLens-owned Calendar + Tasks backend (P2S4).

Self-contained package that powers the calendar/task HTTP endpoints. The
frontend only ever sees the HTTP API (defined in main.py); it is NEVER aware of
Radicale/CalDAV, Taskwarrior, filesystem paths, or backend credentials.

Modules:
  config      - environment-driven configuration (no hard-coded secrets)
  validation  - shared input validation + timezone-aware helpers
  models      - dataclasses matching the frontend CalendarEvent/TaskItem shapes
  calendar_service - CalDAV-backed (Radicale) with a durable local fallback
  task_service     - Taskwarrior CLI-backed, per-account isolated
  reminders   - clean scheduling seam over the existing reminder infrastructure
"""
