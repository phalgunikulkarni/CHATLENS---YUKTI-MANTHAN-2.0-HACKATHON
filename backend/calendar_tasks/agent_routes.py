"""Minimal agent-action endpoint for confirmed Calendar/Task actions (P2S5).

Exposes ONE narrow, validated seam so the frontend can dispatch a CONFIRMED
"Add to Calendar" / "Add Task" action through the existing orchestrator and the
existing functional agents. It does NOT allow arbitrary agent selection or any
Python execution: only the two mutation agents are permitted here, and only
when the caller sets confirmed=true.

  POST /api/agents/action
    body: { "agent": "add_calendar"|"add_task", "confirmed": bool, "params": {...} }
    -> AgentResult JSON (ok, agent, message, data, evidence, metadata, error)

Account isolation: account comes from the resolved X-Account-Id header and is
injected into the AgentContext; a client-supplied account is never trusted.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from account import resolve_account

# Only these two agents may be invoked through this action seam (allowlist).
_ALLOWED_AGENTS = {"add_calendar", "add_task"}


class AgentActionRequest(BaseModel):
    agent: str
    confirmed: bool = False
    params: Dict[str, Any] = Field(default_factory=dict)


def register_agent_action_routes(app: FastAPI) -> None:
    # Build one orchestrator over a registry containing the implemented agents.
    from agents import build_default_registry, Orchestrator, AgentContext

    registry = build_default_registry()
    orchestrator = Orchestrator(registry)

    @app.post("/api/agents/action")
    def agent_action(body: AgentActionRequest, account: str = Depends(resolve_account)):
        if body.agent not in _ALLOWED_AGENTS:
            # Never dispatch arbitrary agents through this mutation seam.
            raise HTTPException(status_code=400, detail="Unsupported agent for this action")

        # Merge confirmation into params; account_id comes ONLY from the header.
        params = dict(body.params or {})
        params["confirmed"] = bool(body.confirmed)

        ctx = AgentContext(account_id=account, params=params)
        result = orchestrator.dispatch(ctx, agent_id=body.agent)

        payload = result.to_dict()
        # Map a controlled agent failure to an appropriate HTTP status while
        # still returning the structured AgentResult body.
        if not payload.get("ok"):
            err = payload.get("error") or ""
            status = 400 if err.startswith("validation") else 422
            raise HTTPException(status_code=status, detail=payload.get("message") or "Action failed")
        return payload
