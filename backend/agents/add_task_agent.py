"""Add Task Agent (functional agent id="add_task").

Turns a CONFIRMED user action into a task via the existing TaskService (P2S4).
Does NOT parse free chat text; does NOT mutate without explicit confirmation.

Params (via AgentContext.params):
  confirmed:  bool  (REQUIRED true to create; otherwise returns a preview)
  title, due_date              (required for creation)
  due_time, priority, completed  (optional; priority defaults to medium)

Account isolation via context.account_id (never trusts client-supplied ids).
Tasks remain tasks — this never creates a calendar event.
"""
from __future__ import annotations


from .contracts import Agent, AgentContext, AgentResult


class AddTaskAgent(Agent):
    id = "add_task"
    description = "Create a task from a confirmed user action (via TaskService)."

    def __init__(self, service=None) -> None:
        self._service = service  # injectable for tests

    def _svc(self):
        if self._service is None:
            from calendar_tasks.task_service import TaskService
            self._service = TaskService()
        return self._service

    def run(self, context: AgentContext) -> AgentResult:
        params = context.params or {}
        account_id = context.account_id
        if not account_id:
            return AgentResult.failure(
                self.id, error="no_account",
                message="No account context; cannot create a task.",
            )

        title = (params.get("title") or "").strip()
        due_date = (params.get("due_date") or "").strip()

        if not bool(params.get("confirmed")):
            return AgentResult.success(
                self.id, message="Confirmation required before creating the task.",
                data={
                    "confirmed": False,
                    "preview": {
                        "title": title, "due_date": due_date,
                        "due_time": params.get("due_time"),
                        "priority": params.get("priority", "medium"),
                    },
                },
                metadata={"requires_confirmation": True},
            )

        try:
            from calendar_tasks.validation import ValidationError
            from calendar_tasks.task_service import TaskServiceError
        except Exception as exc:  # noqa: BLE001
            return AgentResult.failure(self.id, error=f"import_error: {exc}",
                                       message="Task service is unavailable.")

        try:
            task = self._svc().create_task(
                account_id=account_id,
                title=title,
                due_date=due_date,
                due_time=params.get("due_time"),
                priority=params.get("priority", "medium"),
                completed=bool(params.get("completed", False)),
            )
        except ValidationError as exc:
            return AgentResult.failure(self.id, error=f"validation: {exc}",
                                       message=str(exc), data={"confirmed": True})
        except TaskServiceError:
            return AgentResult.failure(self.id, error="task_error",
                                       message="Could not create the task.")

        return AgentResult.success(
            self.id, message="Task Added.",
            data={"confirmed": True, "task": task.to_dict()},
            evidence=[{"type": "task", "id": task.id}],
        )
