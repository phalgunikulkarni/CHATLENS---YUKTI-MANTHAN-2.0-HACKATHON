"""Telegram source connector for ChatLens (Phase 1).

ALL Telegram-specific logic lives in this module. It uses Telethon with a USER
account (MTProto) to connect, fetch recent messages from a target chat, detect
image media, and download those images into a ChatLens-managed local directory.
It then returns enough information for the EXISTING ingestion pipeline
(ml.pipeline.indexer.LibraryIndexer) to index them — this module NEVER performs
OCR/CLIP/BLIP/text-embedding/Chroma/retrieval itself and creates no second
pipeline.

Credentials:
  TELEGRAM_API_ID and TELEGRAM_API_HASH are read from the ENVIRONMENT only
  (never hardcoded, printed, committed, or exposed to the frontend). A local
  ``.env`` file is honored as a convenience if present (parsed without adding a
  dependency), but real values come from the environment.

Session:
  Telethon persists auth in a ``*.session`` file. The default session lives under
  ``<project_root>/telegram_sessions/`` which is git-ignored (along with
  ``*.session`` / ``*.session-journal``). Session files are therefore never
  inside tracked source.

Authentication:
  Uses Telethon's normal user-account auth. The FIRST connect may be interactive
  from the terminal (phone + login code). No frontend OTP/login UI is built in
  Phase 1.

Testability:
  The Telethon client is created via an injectable ``client_factory`` so unit
  tests can supply a fake client with NO network or real credentials.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ChatLens-managed download root for Telegram media. Anchored to the project
# root (two levels above ml/sources/), mirroring how the Chroma DB path is
# anchored, so it resolves consistently regardless of CWD. Git-ignored.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOWNLOAD_DIR = str(PROJECT_ROOT / "data" / "telegram")

# Default Telethon session location (git-ignored directory).
DEFAULT_SESSION_DIR = str(PROJECT_ROOT / "telegram_sessions")
DEFAULT_SESSION_NAME = "chatlens_user"

# Image extensions ChatLens indexes (mirrors the scanner's supported set).
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}

SOURCE_NAME = "telegram"


class TelegramCredentialsError(RuntimeError):
    """Raised when TELEGRAM_API_ID / TELEGRAM_API_HASH are missing/invalid."""


@dataclass
class TelegramImage:
    """One downloaded Telegram image plus its provenance metadata.

    ``file_path`` points at the downloaded, ChatLens-managed copy — this is what
    the existing ingestion pipeline consumes. The metadata fields are retained
    internally for Phase 2 (they are NOT yet written into Chroma here).
    """

    file_path: str
    message_id: int
    chat_id: Any
    chat_name: Optional[str] = None
    timestamp: Optional[str] = None       # ISO 8601 message date, if available
    caption: Optional[str] = None
    source: str = SOURCE_NAME

    def to_metadata(self) -> Dict[str, Any]:
        """Provenance dict (for later Chroma extra_metadata; additive-only)."""
        md: Dict[str, Any] = {
            "source": self.source,
            "telegram_message_id": self.message_id,
            "telegram_chat_id": str(self.chat_id),
        }
        if self.chat_name:
            md["telegram_chat_name"] = self.chat_name
        if self.timestamp:
            md["telegram_timestamp"] = self.timestamp
        if self.caption:
            md["telegram_caption"] = self.caption
        return md


@dataclass
class FetchReport:
    """Summary of one fetch/download run (honest counts; no fabrication)."""

    chat: str = ""
    scanned_messages: int = 0
    image_messages: int = 0
    downloaded: int = 0
    skipped_non_image: int = 0
    failed_downloads: int = 0
    images: List[TelegramImage] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _load_env_file_once() -> None:
    """Best-effort: populate os.environ from a local ``.env`` if the vars are
    not already set. No dependency; only sets keys that are absent so real
    environment values always win. Never prints values.
    """
    if os.environ.get("TELEGRAM_API_ID") and os.environ.get("TELEGRAM_API_HASH"):
        return
    env_path = PROJECT_ROOT / ".env"
    try:
        if not env_path.is_file():
            return
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        # A missing/unreadable .env is non-fatal; env vars may still be set.
        return


def load_credentials() -> tuple:
    """Return (api_id:int, api_hash:str) from the environment.

    Raises TelegramCredentialsError with a clear message (NO secret values) when
    missing or malformed. Never logs the credentials.
    """
    _load_env_file_once()
    raw_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    if not raw_id or not api_hash:
        missing = [n for n, v in (("TELEGRAM_API_ID", raw_id),
                                  ("TELEGRAM_API_HASH", api_hash)) if not v]
        raise TelegramCredentialsError(
            "Missing Telegram credentials in environment: " + ", ".join(missing)
        )
    try:
        api_id = int(str(raw_id).strip())
    except ValueError as exc:
        raise TelegramCredentialsError("TELEGRAM_API_ID must be an integer") from exc
    return api_id, api_hash


def _is_image_message(message: Any) -> bool:
    """True if a Telethon message carries an eligible IMAGE.

    Supports:
      - photo messages (message.photo)
      - image documents whose mime-type starts with 'image/' (e.g. image/png),
        excluding animated/GIF-like which are not in our indexed set.
    Ignores text-only, video, audio, and arbitrary documents. Never raises.
    """
    try:
        if getattr(message, "photo", None):
            return True
        doc = getattr(message, "document", None)
        if doc is not None:
            mime = (getattr(doc, "mime_type", "") or "").lower()
            if mime.startswith("image/") and mime not in ("image/gif",):
                return True
        return False
    except Exception:
        return False


class TelegramSource:
    """Connect to Telegram (user account) and download image media.

    Downloads flow into the existing ChatLens ingestion pipeline via the
    returned file paths; this class does not index anything itself.
    """

    def __init__(
        self,
        session: Optional[str] = None,
        download_dir: str = DEFAULT_DOWNLOAD_DIR,
        client_factory: Optional[Callable[[str, int, str], Any]] = None,
    ) -> None:
        """
        Args:
            session: Telethon session name/path. Defaults to a git-ignored path
                under ``telegram_sessions/``.
            download_dir: ChatLens-managed directory for downloaded images.
            client_factory: (api_id, api_hash) -> Telethon client. Injectable so
                tests can provide a fake client. Defaults to a real
                TelegramClient created lazily (import deferred).
        """
        self._session = session or os.path.join(DEFAULT_SESSION_DIR, DEFAULT_SESSION_NAME)
        self._download_dir = download_dir
        self._client_factory = client_factory
        self._client = None

    # -- connection -----------------------------------------------------------

    def _default_client_factory(self, session: str, api_id: int, api_hash: str) -> Any:
        # Import Telethon lazily so the module imports cheaply and unit tests
        # (which inject a fake) never require telethon or network.
        from telethon.sync import TelegramClient
        os.makedirs(os.path.dirname(session) or ".", exist_ok=True)
        return TelegramClient(session, api_id, api_hash)

    def connect(self) -> Any:
        """Create/reuse the Telethon client and start the user session.

        Reads credentials from the environment (raising TelegramCredentialsError
        if missing). The first call may prompt interactively in the terminal for
        phone + login code (Telethon's normal user auth). Returns the client.
        """
        if self._client is not None:
            return self._client
        api_id, api_hash = load_credentials()
        factory = self._client_factory or self._default_client_factory
        client = factory(self._session, api_id, api_hash)
        # Telethon's .start() performs interactive login on first run and reuses
        # the persisted session thereafter. A fake client in tests may no-op.
        start = getattr(client, "start", None)
        if callable(start):
            start()
        self._client = client
        return client

    # -- fetch + download -----------------------------------------------------

    def fetch_images(self, chat: Any, limit: int = 20) -> FetchReport:
        """Fetch up to ``limit`` recent messages from ``chat`` and download the
        image ones into the managed directory.

        - Only photo/image-document messages are downloaded; everything else is
          counted as skipped_non_image.
        - A download failure for ONE message is recorded and does not abort the
          rest of the batch.
        - Returns a FetchReport with per-image TelegramImage records (file path +
          provenance metadata).
        """
        report = FetchReport(chat=str(chat))
        client = self.connect()
        os.makedirs(self._download_dir, exist_ok=True)

        try:
            messages = client.get_messages(chat, limit=limit)
        except Exception as exc:  # noqa: BLE001 - network/API failure is reported, not raised
            report.errors.append(f"get_messages failed: {exc}")
            return report

        chat_name = self._resolve_chat_name(client, chat)

        for message in messages or []:
            report.scanned_messages += 1
            if not _is_image_message(message):
                report.skipped_non_image += 1
                continue
            report.image_messages += 1
            try:
                dest = self._download_one(client, message)
                if not dest:
                    report.failed_downloads += 1
                    continue
                report.downloaded += 1
                report.images.append(TelegramImage(
                    file_path=dest,
                    message_id=int(getattr(message, "id", 0) or 0),
                    chat_id=getattr(message, "chat_id", None) or chat,
                    chat_name=chat_name,
                    timestamp=self._iso_date(getattr(message, "date", None)),
                    caption=(getattr(message, "message", None) or None),
                ))
            except Exception as exc:  # noqa: BLE001 - isolate per-message failure
                report.failed_downloads += 1
                report.errors.append(f"message {getattr(message, 'id', '?')}: {exc}")
                continue
        return report

    def _download_one(self, client: Any, message: Any) -> Optional[str]:
        """Download one message's media into the managed dir. Returns the final
        path, or None if nothing eligible was written.

        The filename incorporates the chat+message id for stability and to avoid
        collisions; the resulting on-disk path is what feeds the existing
        indexer (which derives its own stable image_id from the path).
        """
        mid = getattr(message, "id", None)
        base = os.path.join(self._download_dir, f"tg_{getattr(message, 'chat_id', 'chat')}_{mid}")
        # Telethon picks the extension from the media; we pass a base file path.
        out = client.download_media(message, file=base)
        if not out:
            return None
        # Only keep eligible image extensions; ignore anything else that slipped
        # through (defensive — _is_image_message already filtered).
        if os.path.splitext(str(out))[1].lower() not in _ALLOWED_EXT:
            return None
        return str(out)

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _iso_date(date_val: Any) -> Optional[str]:
        if date_val is None:
            return None
        try:
            return date_val.isoformat()
        except Exception:
            return str(date_val)

    @staticmethod
    def _resolve_chat_name(client: Any, chat: Any) -> Optional[str]:
        try:
            entity = client.get_entity(chat)
        except Exception:
            return None
        for attr in ("title", "username", "first_name"):
            val = getattr(entity, attr, None)
            if val:
                return str(val)
        return None

    @property
    def download_dir(self) -> str:
        return self._download_dir

    @property
    def session_path(self) -> str:
        return self._session
