"""Mocked unit tests for ml/sources/telegram_source.py (Phase 1).

No real Telegram credentials or network: a fake Telethon client is injected via
``client_factory`` and credentials are set through env vars in-test. Verifies:
  - env credentials loaded (and clear error when missing)
  - photo message detected; text-only ignored; video/audio ignored
  - image-document (mime image/*) detected
  - metadata extraction (message id, chat, timestamp, caption, source=telegram)
  - download success writes into the managed dir
  - one download failure does not stop the others
  - configurable message limit is honored
  - session path is NOT inside tracked source (git-ignored location)

Standard-library unittest; no new testing dependency.
"""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.sources import telegram_source as ts  # noqa: E402
from ml.sources.telegram_source import (  # noqa: E402
    TelegramSource, TelegramCredentialsError, load_credentials, _is_image_message,
)


# --- Fake Telethon message/media/client (no network) ---

def _photo_msg(mid, caption=None, chat_id=-100):
    return SimpleNamespace(
        id=mid, chat_id=chat_id, message=caption,
        date=datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        photo=object(), document=None,
    )

def _text_msg(mid, chat_id=-100):
    return SimpleNamespace(id=mid, chat_id=chat_id, message="hello",
                           date=None, photo=None, document=None)

def _video_msg(mid, chat_id=-100):
    doc = SimpleNamespace(mime_type="video/mp4")
    return SimpleNamespace(id=mid, chat_id=chat_id, message=None,
                           date=None, photo=None, document=doc)

def _image_doc_msg(mid, chat_id=-100):
    doc = SimpleNamespace(mime_type="image/png")
    return SimpleNamespace(id=mid, chat_id=chat_id, message="doc caption",
                           date=None, photo=None, document=doc)


class _FakeClient:
    """Fake Telethon client. ``fail_ids`` -> download raises for those ids."""
    def __init__(self, messages, out_dir, fail_ids=None, entity_title="Test Chat"):
        self._messages = messages
        self._out_dir = out_dir
        self._fail_ids = fail_ids or set()
        self._entity_title = entity_title
        self.started = False

    def start(self):
        self.started = True

    def get_messages(self, chat, limit=20):
        return list(self._messages)[:limit]

    def get_entity(self, chat):
        return SimpleNamespace(title=self._entity_title)

    def download_media(self, message, file=None):
        if message.id in self._fail_ids:
            raise RuntimeError("simulated download failure")
        # Emulate Telethon writing <base>.jpg and returning the final path.
        dest = f"{file}.jpg"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\nfake")
        return dest


class TelegramCredentialsTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_credentials_loaded_from_env(self):
        os.environ["TELEGRAM_API_ID"] = "123456"
        os.environ["TELEGRAM_API_HASH"] = "abcdef0123456789"
        api_id, api_hash = load_credentials()
        self.assertEqual(api_id, 123456)
        self.assertEqual(api_hash, "abcdef0123456789")

    def test_missing_credentials_raise_clear_error(self):
        # Neutralize BOTH sources of credentials deterministically: clear the
        # env vars AND stub the .env fallback to a no-op, so this test proves
        # the missing-credentials path regardless of a local .env file.
        from unittest import mock
        os.environ.pop("TELEGRAM_API_ID", None)
        os.environ.pop("TELEGRAM_API_HASH", None)
        with mock.patch.object(ts, "_load_env_file_once", lambda: None):
            with self.assertRaises(TelegramCredentialsError):
                load_credentials()


class ImageDetectionTests(unittest.TestCase):
    def test_photo_detected(self):
        self.assertTrue(_is_image_message(_photo_msg(1)))

    def test_text_ignored(self):
        self.assertFalse(_is_image_message(_text_msg(2)))

    def test_video_ignored(self):
        self.assertFalse(_is_image_message(_video_msg(3)))

    def test_image_document_detected(self):
        self.assertTrue(_is_image_message(_image_doc_msg(4)))


class FetchImagesTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH")}
        os.environ["TELEGRAM_API_ID"] = "111"
        os.environ["TELEGRAM_API_HASH"] = "hashvalue"
        self._tmp = Path(__file__).resolve().parent / "_tg_tmp"
        self._tmp.mkdir(exist_ok=True)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for f in self._tmp.rglob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            self._tmp.rmdir()
        except OSError:
            pass

    def _source(self, messages, fail_ids=None):
        fake = _FakeClient(messages, str(self._tmp), fail_ids=fail_ids)
        return TelegramSource(
            session=str(self._tmp / "s" / "chatlens_user"),
            download_dir=str(self._tmp),
            client_factory=lambda session, api_id, api_hash: fake,
        ), fake

    def test_download_success_and_metadata(self):
        src, _ = self._source([_photo_msg(10, caption="a cat")])
        report = src.fetch_images("@testchat", limit=20)
        self.assertEqual(report.downloaded, 1)
        img = report.images[0]
        self.assertTrue(os.path.isfile(img.file_path))
        self.assertEqual(img.message_id, 10)
        self.assertEqual(img.caption, "a cat")
        self.assertEqual(img.source, "telegram")
        self.assertEqual(img.chat_name, "Test Chat")
        self.assertIsNotNone(img.timestamp)
        md = img.to_metadata()
        self.assertEqual(md["source"], "telegram")
        self.assertEqual(md["telegram_message_id"], 10)

    def test_text_and_video_ignored(self):
        src, _ = self._source([_photo_msg(1), _text_msg(2), _video_msg(3)])
        report = src.fetch_images("@testchat")
        self.assertEqual(report.downloaded, 1)
        self.assertEqual(report.skipped_non_image, 2)

    def test_one_failure_does_not_stop_others(self):
        src, _ = self._source(
            [_photo_msg(1), _photo_msg(2), _photo_msg(3)], fail_ids={2},
        )
        report = src.fetch_images("@testchat")
        self.assertEqual(report.downloaded, 2)       # 1 and 3 succeed
        self.assertEqual(report.failed_downloads, 1)  # 2 failed, isolated
        self.assertEqual({i.message_id for i in report.images}, {1, 3})

    def test_configurable_limit(self):
        msgs = [_photo_msg(i) for i in range(1, 11)]
        src, fake = self._source(msgs)
        report = src.fetch_images("@testchat", limit=3)
        self.assertEqual(report.scanned_messages, 3)
        self.assertEqual(report.downloaded, 3)

    def test_session_path_not_inside_tracked_source(self):
        # Default session lives under the git-ignored telegram_sessions/ dir.
        src = TelegramSource(client_factory=lambda s, a, h: _FakeClient([], "."))
        self.assertIn("telegram_sessions", src.session_path.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
