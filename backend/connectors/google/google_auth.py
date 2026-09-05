"""Google Photos OAuth for ChatLens.

Migrated to the Google Photos **Picker API** scope. The legacy
`photoslibrary.readonly` scope was removed by Google on 2025-03-31 and
`mediaItems.list` now returns 403 for a real user library, so the read/fetch
path must go through the user-driven Picker (see google_sync.py).

Security hardening applied here:
- Scope is the Picker read-only scope only.
- Client-secret path and redirect URI come from the environment (never
  hardcoded); the client_secret.json contents and token values are never
  logged.
- OAuth `state` is a cryptographically-random, single-use, server-side token
  (see create_state / consume_state) instead of the account_id itself.
"""

import os
import json
import logging
import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from models import OAuthState

# The Google auth libraries are imported lazily inside the functions that need
# them. This keeps the module importable (for tests and for environments that
# only exercise the state/credential-file logic) without requiring the full
# google-auth stack to be installed.

logger = logging.getLogger(__name__)

# Picker read-only scope (replaces the removed photoslibrary.readonly scope).
SCOPES = ['https://www.googleapis.com/auth/photospicker.mediaitems.readonly']

# Directory holding the per-account credential files (JSON, not pickle).
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# How long a minted OAuth state remains valid before it is considered expired.
STATE_TTL = timedelta(minutes=10)


class GoogleAuthError(Exception):
    """Typed error the API layer maps to connector status 'error'.

    Raised for recoverable-at-the-user-level problems (revoked/failed refresh,
    missing/invalid state) so callers never loop-fail on them.
    """


def _client_secret_file() -> str:
    """Resolve the client secret path from env, falling back to backend root."""
    env_path = os.environ.get("GOOGLE_CLIENT_SECRET_FILE")
    if env_path:
        return env_path
    return os.path.join(os.path.dirname(__file__), "..", "..", "client_secret.json")


def _redirect_uri() -> str:
    return os.environ.get(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/api/connectors/google/callback",
    )


def _require_client_secret() -> str:
    path = _client_secret_file()
    if not os.path.exists(path):
        # Do NOT log the path contents; only that it is missing.
        logger.error("Google client secret file not found.")
        raise FileNotFoundError(
            "Missing Google client secret. Set GOOGLE_CLIENT_SECRET_FILE or add "
            "backend/client_secret.json."
        )
    return path


def _session_file(account_id: str) -> str:
    # account_id is server-resolved (never raw user input from the frontend);
    # keep the filename simple and deterministic.
    safe = str(account_id).replace(os.sep, "_").replace("/", "_")
    return os.path.join(SESSIONS_DIR, f"{safe}_google.json")


# ---------------------------------------------------------------------------
# Secure OAuth state (single-use, server-side, expiring)
# ---------------------------------------------------------------------------
def create_state(account_id: str, db: Session) -> str:
    """Mint a cryptographically-random, single-use state mapped to account_id."""
    state = secrets.token_urlsafe(32)
    row = OAuthState(
        state=state,
        account_id=account_id,
        created_at=datetime.now(timezone.utc),
        used=0,
    )
    db.add(row)
    db.commit()
    return state


def consume_state(state: str, db: Session) -> str | None:
    """Resolve and invalidate a state. Returns account_id or None.

    Rejects unknown, expired (> STATE_TTL), or already-used states. The state is
    marked used (single-use) on the first successful resolution.
    """
    if not state:
        return None
    row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if row is None:
        return None
    if row.used:
        return None

    created = row.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created is None or datetime.now(timezone.utc) - created > STATE_TTL:
        # Expired: consume it so it cannot be retried.
        row.used = 1
        db.commit()
        return None

    account_id = row.account_id
    row.used = 1
    db.commit()
    return account_id


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------
def get_auth_url(account_id: str, db: Session) -> str:
    """Generate the Google auth URL using a secure, minted state."""
    client_secret = _require_client_secret()

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        client_secret,
        scopes=SCOPES,
        redirect_uri=_redirect_uri(),
    )

    # PKCE disabled: confidential server-side client (has client secret) and
    # exchange_code() uses a SEPARATE Flow instance, so a verifier generated
    # here would be unavailable at token exchange (fetch_token would fail).
    flow.autogenerate_code_verifier = False
    state = create_state(account_id, db)
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state,
    )
    return auth_url


def exchange_code(code: str, state: str, db: Session) -> str:
    """Exchange the auth code for credentials and persist them.

    The account is resolved from the single-use `state` (never trusted as the
    account_id). Returns the resolved account_id. Raises GoogleAuthError if the
    state is invalid/expired/used.
    """
    account_id = consume_state(state, db)
    if account_id is None:
        raise GoogleAuthError("Invalid, expired, or already-used OAuth state.")

    client_secret = _require_client_secret()

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        client_secret,
        scopes=SCOPES,
        redirect_uri=_redirect_uri(),
    )

    flow.fetch_token(code=code)
    credentials = flow.credentials
    _save_credentials(account_id, credentials)
    return account_id


def _save_credentials(account_id: str, credentials) -> None:
    """Persist credentials as JSON (no pickle). Token values are never logged."""
    data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
    }
    with open(_session_file(account_id), "w", encoding="utf-8") as f:
        json.dump(data, f)


# Module-level hook so tests can monkeypatch `google_auth.Credentials`. When it
# is None it is lazily resolved to the real google.oauth2.credentials class.
Credentials = None


def _credentials_class():
    global Credentials
    if Credentials is None:
        from google.oauth2.credentials import Credentials as _Credentials
        Credentials = _Credentials
    return Credentials


# Module-level hook for the refresh-error type. Defaults to google's
# RefreshError when the library is installed, otherwise a local stand-in so the
# module (and tests) work without the google-auth stack. Tests raise this exact
# class from a fake `.refresh` to exercise the failure path.
try:  # pragma: no cover - depends on environment
    from google.auth.exceptions import RefreshError as RefreshError
except Exception:  # noqa: BLE001
    class RefreshError(Exception):  # type: ignore[no-redef]
        """Stand-in used when google-auth is not installed."""


def _refresh_helpers():
    """Return (Request instance or None, RefreshError class), imported lazily."""
    try:
        from google.auth.transport.requests import Request
        request_obj = Request()
    except Exception:  # noqa: BLE001 - transport unavailable in slim test env
        request_obj = None
    return request_obj, RefreshError


def get_credentials(account_id: str):
    """Load saved credentials, refreshing if expired.

    Returns None if the account has no stored credentials. Raises
    GoogleAuthError if a required refresh fails or the grant was revoked â€” the
    caller maps this to connector status 'error' (never loop-fails).
    """
    session_file = _session_file(account_id)
    if not os.path.exists(session_file):
        return None

    with open(session_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    credentials = _credentials_class()(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", SCOPES),
    )

    if credentials.expired and credentials.refresh_token:
        request_obj, refresh_error = _refresh_helpers()
        try:
            credentials.refresh(request_obj)
        except refresh_error as e:
            # Do not log token contents; surface a typed error.
            logger.warning("Google credential refresh failed (revoked or invalid grant).")
            raise GoogleAuthError("Google credential refresh failed.") from e
        _save_credentials(account_id, credentials)

    return credentials
