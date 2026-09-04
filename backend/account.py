"""Account Identity Bridge (backend resolve side).

Phase 1 of account-scoped-chat-and-isolation. The frontend transmits its
existing dev-only stable account id (``stableAccountId(email) => acct-<hex>``)
as the ``X-Account-Id`` HTTP header. This module resolves and validates that
header into an ``account_id`` for user-owned endpoints.

This is APPLICATION-LEVEL attribution, NOT security-grade authentication: the
header is client-supplied and therefore spoofable. That is a documented,
accepted Phase-1 limitation (see the spec). No JWT/passwords are introduced.
"""

import re

from fastapi import Header, HTTPException

# Account_Id form produced by the frontend DevAuthService.stableAccountId(email).
ACCOUNT_RE = re.compile(r"^acct-[0-9a-f]+$")


def resolve_account(x_account_id: str | None = Header(default=None)) -> str:
    """Resolve the owning account from the ``X-Account-Id`` request header.

    FastAPI maps the ``x_account_id`` parameter to the ``X-Account-Id`` header.
    When the header is missing or does not match ``^acct-[0-9a-f]+$`` the
    request is rejected with HTTP 401 and NO data access is performed on the
    reject path. Otherwise the header value is returned unchanged.
    """
    if not x_account_id or not ACCOUNT_RE.match(x_account_id):
        raise HTTPException(status_code=401, detail="Missing or invalid account identity")
    return x_account_id
