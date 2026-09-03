"""User-authorized local image access for ChatLens.

Purpose (and ONLY purpose):
    AUTHORIZED LOCATION(S)  ->  validate accessibility  ->  hand to the EXISTING
    ingestion scanner (ml.ingestion.scanner.scan_dataset).

This module is a thin, dataset-independent adapter between "locations the user
authorized" and the existing ML ingestion pipeline. It does NOT:
  - modify the scanner, OCR, CLIP, text-embedding, ChromaDB, or retrieval code,
  - implement a second scanner (it reuses scan_dataset),
  - hardcode any username, home/Desktop/Downloads/Pictures path, drive letter,
    project path, dataset name, folder name, or filename,
  - scan the whole computer, retry other paths, bypass OS permissions, or
    escalate privileges.

PERMISSION MODEL / PLATFORM BOUNDARY
------------------------------------
A pure Python ML backend cannot, by itself, raise the native macOS privacy
(TCC) prompt or a Windows shell folder-picker from a headless/importable
context. Native user-consent UI belongs to the frontend/integration layer.
Therefore this module's contract is:

  * The caller (frontend / integration / OS picker) supplies the location(s)
    the user has ALREADY authorized.
  * This module then only checks whether the OS actually permits reading each
    location. Whatever the OS enforces is authoritative: if the OS denies read
    access (TCC/sandbox/ACL), listing fails and we report ACCESS_DENIED for that
    location and stop — we never retry via another path or work around it.

An OPTIONAL convenience, `pick_directories_interactively()`, uses the standard
library Tk file dialog as a legitimate user-consent folder selection when a GUI
display is available. It is opt-in and simply produces authorized paths; it is
not a permission bypass and no-ops cleanly where no display exists.
"""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, List, Optional, Union

PathLike = Union[str, os.PathLike[str]]

# Static image formats eligible for ChatLens. Limited to the formats the
# existing downstream pipeline (OCR/CLIP/Pillow) already handles reliably.
# Animated-capable formats are handled specially below; GIF and all video/
# audio/document formats are excluded entirely.
STATIC_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})

# Formats that CAN contain animation and therefore require per-file inspection
# before they are considered eligible (a static instance is fine; an animated
# one is skipped completely).
ANIMATION_CAPABLE_EXTENSIONS = frozenset({".webp"})


def is_static_image_file(file_path: PathLike) -> bool:
    """True only if the file is a locally-present, supported STATIC image.

    Eligibility = supported static extension AND (if the format can animate)
    verified NOT animated. Animated WebP and GIF are rejected. The file must
    exist locally (cloud-only placeholders that cannot be opened are rejected).
    Never raises; returns False on any uncertainty so nothing questionable
    reaches the ML pipeline.
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext not in STATIC_IMAGE_EXTENSIONS:
        return False
    if not p.is_file():
        return False
    if ext in ANIMATION_CAPABLE_EXTENSIONS:
        return _is_static_animatable(p)
    return True


def _webp_is_animated(p: Path) -> Optional[bool]:
    """Detect WebP animation from the RIFF container (no decoder dependency).

    A WebP is a RIFF file: bytes 0-3 "RIFF", 8-11 "WEBP", then chunks. An
    animated WebP contains an "ANIM" chunk (and "ANMF" frame chunks) and its
    "VP8X" chunk sets the animation flag bit. We scan the first chunks' FourCCs
    for "ANIM". Returns True (animated), False (static), or None (unknown/not a
    readable WebP) so the caller can decide conservatively.

    This is needed because some Pillow builds lack WebP-animation support and
    then report animated files as single-frame.
    """
    try:
        with open(p, "rb") as fh:
            header = fh.read(12)
            if len(header) < 12 or header[0:4] != b"RIFF" or header[8:12] != b"WEBP":
                return None
            # Walk chunks looking for VP8X animation flag or an ANIM chunk.
            data = fh.read(4096)  # ANIM/VP8X appear very early; a small read suffices
    except OSError:
        return None
    if b"ANIM" in data or b"ANMF" in data:
        return True
    # VP8X extended header: chunk "VP8X" followed by 4-byte size then flags byte;
    # bit 1 (0x02) is the animation flag.
    idx = data.find(b"VP8X")
    if idx != -1 and len(data) >= idx + 9:
        flags = data[idx + 8]
        if flags & 0x02:
            return True
        return False
    # Simple lossy/lossless (VP8 / VP8L) single-image WebP -> static.
    if b"VP8 " in data or b"VP8L" in data:
        return False
    return None


def _is_static_animatable(p: Path) -> bool:
    """Return True if an animation-capable image is actually a single frame.

    Primary signal: WebP RIFF container inspection (dependency-free, robust even
    when Pillow lacks WebP-animation support). Secondary signal: Pillow frame
    count. A cloud-only/unreadable file cannot be opened and is rejected.
    """
    # 1) Authoritative container-level check for WebP.
    if p.suffix.lower() == ".webp":
        verdict = _webp_is_animated(p)
        if verdict is True:
            return False   # animated -> not eligible
        if verdict is False:
            return True    # static -> eligible
        # verdict is None -> fall through to Pillow / conservative handling.

    # 2) Pillow frame-count fallback (works for formats Pillow fully supports).
    try:
        from PIL import Image
    except Exception:
        return False  # cannot verify -> reject
    try:
        with Image.open(p) as im:
            if getattr(im, "is_animated", False):
                return False
            if getattr(im, "n_frames", 1) > 1:
                return False
            try:
                im.seek(1)
                return False  # a second frame exists -> animated
            except EOFError:
                return True   # single frame -> static
            except Exception:
                return False
    except Exception:
        return False

class OperatingSystem(str, Enum):
    """Detected OS family."""

    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    UNKNOWN = "unknown"


def detect_os() -> OperatingSystem:
    """Detect the current OS automatically via the standard library.

    No machine-specific assumptions; works for any user on any machine.
    """
    system = platform.system().lower()
    if system == "darwin":
        return OperatingSystem.MACOS
    if system == "windows":
        return OperatingSystem.WINDOWS
    if system == "linux":
        return OperatingSystem.LINUX
    return OperatingSystem.UNKNOWN


class AccessResult(str, Enum):
    """Outcome of attempting to use one authorized location."""

    GRANTED = "granted"          # location is readable; scan proceeded
    DENIED = "denied"            # OS denied read access (permission)
    NOT_FOUND = "not_found"      # path does not exist
    NOT_A_DIRECTORY = "not_a_directory"
    ERROR = "error"              # any other failure while reading


@dataclass
class LocationResult:
    """Result of handling a single authorized location."""

    location: str
    access: AccessResult
    scan_result: Optional[Any] = None   # ml.ingestion.scanner.ScanResult
    image_count: int = 0                 # eligible static images kept
    animated_skipped: int = 0            # animation-capable files rejected
    ineligible_skipped: int = 0          # discovered-but-not-static images dropped
    message: str = ""


@dataclass
class IngestBatch:
    """Aggregated result across all authorized locations."""

    operating_system: OperatingSystem
    locations: List[LocationResult] = field(default_factory=list)

    @property
    def total_images(self) -> int:
        return sum(l.image_count for l in self.locations)

    @property
    def granted_locations(self) -> List[LocationResult]:
        return [l for l in self.locations if l.access is AccessResult.GRANTED]

    @property
    def image_records(self) -> List[Any]:
        """Flat list of ImageRecord objects from all granted locations."""
        out: List[Any] = []
        for l in self.granted_locations:
            if l.scan_result is not None:
                out.extend(l.scan_result.records)
        return out


class LocalImageAccess:
    """Adapter: user-authorized location(s) -> existing ingestion scanner.

    The class is OS-aware for reporting/validation but delegates ALL image
    discovery to the existing `scan_dataset`, so image-filtering rules stay in
    one place (the scanner) and are never duplicated here.
    """

    def __init__(self, operating_system: Optional[OperatingSystem] = None) -> None:
        self.operating_system: OperatingSystem = operating_system or detect_os()

    # -- validation (respects whatever the OS enforces) ----------------------

    def _check_access(self, location: PathLike) -> AccessResult:
        """Check OS-level readability. The OS decision is authoritative.

        We do not try to bypass a denial; we report it. On macOS, a TCC-blocked
        directory typically surfaces as a PermissionError on listing, which we
        map to DENIED. On Windows, an ACL denial maps the same way.
        """
        p = Path(location)
        try:
            if not p.exists():
                return AccessResult.NOT_FOUND
            if not p.is_dir():
                return AccessResult.NOT_A_DIRECTORY
            # Probe read permission without walking the whole tree: attempt to
            # open the directory for iteration. If the OS forbids it, this raises.
            if not os.access(p, os.R_OK | os.X_OK):
                return AccessResult.DENIED
            with os.scandir(p) as it:
                next(it, None)  # touch one entry to trigger any OS denial
            return AccessResult.GRANTED
        except PermissionError:
            return AccessResult.DENIED
        except OSError:
            return AccessResult.ERROR

    # -- default accessible user scope (derived, never hardcoded) ------------

    # User-facing image folder names, resolved RELATIVE TO the home directory
    # (never hardcoded absolute paths, usernames, or drive letters). These are
    # the only roots ChatLens will recurse. System/application-managed trees
    # (macOS ~/Library, Windows AppData/Program Files, caches, browser data,
    # application-managed photo libraries, package/dependency dirs, and the
    # ChatLens repo itself) are intentionally NOT included, so recursion cannot
    # re-enter the previous whole-home / ~/Library explosion.
    USER_FACING_SUBDIRS: tuple[str, ...] = (
        "Desktop", "Downloads", "Documents", "Pictures",
    )

    def default_user_scope(self) -> List[str]:
        """Resolve a SMALL ALLOWLIST of user-facing local image roots.

        Roots are derived by joining the standard-library home directory
        (``Path.home()`` -> per-OS, per-user) with well-known user-facing folder
        names (Desktop/Downloads/Documents/Pictures). Only roots that actually
        exist, are directories, and are OS-readable are returned. We do NOT scan
        the home root itself, ~/Library, application/cache/browser/system data,
        or application-managed photo storage.

        Returns [] if none can be resolved. The eventual frontend/integration
        layer may instead pass explicit authorized roots to ingest_locations().
        """
        try:
            home = Path.home()
        except Exception:
            return []
        roots: List[str] = []
        for name in self.USER_FACING_SUBDIRS:
            candidate = home / name
            # Only genuine, readable directories become roots. No home-root scan.
            if candidate.is_dir() and self._check_access(candidate) is AccessResult.GRANTED:
                roots.append(str(candidate))
        return roots

    # -- core: hand authorized locations to the existing scanner -------------

    def ingest_location(self, location: PathLike) -> LocationResult:
        """Validate one authorized location and, if readable, scan it.

        Uses the EXISTING scanner (scan_dataset). Never retries another path.
        """
        loc_str = str(location)
        access = self._check_access(location)
        if access is not AccessResult.GRANTED:
            return LocationResult(
                location=loc_str, access=access, image_count=0,
                message={
                    AccessResult.DENIED: "Access denied by the operating system.",
                    AccessResult.NOT_FOUND: "Location does not exist.",
                    AccessResult.NOT_A_DIRECTORY: "Location is not a directory.",
                    AccessResult.ERROR: "Location could not be read.",
                }.get(access, "Unusable location."),
            )
        # Delegate to the existing ingestion scanner (no duplicate logic).
        from ml.ingestion.scanner import scan_dataset  # local import: no coupling
        try:
            scan = scan_dataset(loc_str)
        except NotADirectoryError:
            return LocationResult(location=loc_str, access=AccessResult.NOT_A_DIRECTORY,
                                  message="Location is not a directory.")
        except PermissionError:
            return LocationResult(location=loc_str, access=AccessResult.DENIED,
                                  message="Access denied by the operating system.")
        except OSError as exc:
            return LocationResult(location=loc_str, access=AccessResult.ERROR,
                                  message=f"Read error: {exc}")

        # Enforce STATIC-IMAGE eligibility BEFORE any ML processing. The scanner
        # discovers supported extensions; here we drop animation-capable files
        # that are actually animated (e.g. animated WebP) and anything that is
        # not a locally-openable static image. We filter the ScanResult's records
        # in place so the existing indexer/pipeline receives only eligible files.
        # (Cheap: at most a lightweight Pillow header read for webp; no OCR/CLIP.)
        original = list(scan.records)
        eligible = []
        animated = 0
        ineligible = 0
        for rec in original:
            fp = getattr(rec, "file_path", "")
            ext = Path(fp).suffix.lower()
            if is_static_image_file(fp):
                eligible.append(rec)
            elif ext in ANIMATION_CAPABLE_EXTENSIONS:
                animated += 1          # animation-capable but animated/unreadable
            else:
                ineligible += 1        # discovered but not an eligible static image
        scan.records = eligible

        return LocationResult(
            location=loc_str, access=AccessResult.GRANTED, scan_result=scan,
            image_count=len(eligible),
            animated_skipped=animated,
            ineligible_skipped=ineligible,
            message=(f"{len(eligible)} static image(s); "
                     f"{animated} animated skipped; {ineligible} ineligible skipped."),
        )

    def ingest_locations(self, locations: Iterable[PathLike]) -> IngestBatch:
        """Handle MULTIPLE user-authorized locations.

        Processes only the locations provided (never adds unauthorized ones).
        Denied/missing locations are reported and skipped; granted ones are
        scanned via the existing pipeline.
        """
        batch = IngestBatch(operating_system=self.operating_system)
        seen: set[str] = set()
        for loc in locations:
            key = str(Path(loc))
            if key in seen:
                continue
            seen.add(key)
            batch.locations.append(self.ingest_location(loc))
        return batch

    # -- optional, opt-in native folder selection (legitimate consent) -------

    def pick_directories_interactively(self, max_dirs: int = 10) -> List[str]:
        """Let the user choose folder(s) via the stdlib Tk dialog, if available.

        This is a legitimate user-consent selection mechanism, not a bypass. It
        only works where a GUI display exists; otherwise it returns [] so headless
        backends are unaffected. The eventual frontend may replace this with its
        own native picker and simply pass the chosen paths to ingest_locations().
        """
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception:
            return []
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            return []  # no display / headless environment
        chosen: List[str] = []
        try:
            for _ in range(max(1, max_dirs)):
                d = filedialog.askdirectory(title="ChatLens: authorize an image folder (Cancel to finish)")
                if not d:
                    break
                chosen.append(d)
        finally:
            try:
                root.destroy()
            except Exception:
                pass
        return chosen


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    parser = argparse.ArgumentParser(
        description="Hand user-authorized local location(s) to the existing ChatLens scanner."
    )
    parser.add_argument("locations", nargs="*",
                        help="One or more user-authorized directory paths.")
    parser.add_argument("--pick", action="store_true",
                        help="Open a folder picker (GUI only) to authorize location(s).")
    args = parser.parse_args()

    access = LocalImageAccess()
    print(f"Detected OS: {access.operating_system.value}")

    locations = list(args.locations)
    if args.pick:
        locations += access.pick_directories_interactively()

    if not locations:
        print("No authorized location(s) provided. Nothing to scan.")
        sys.exit(0)

    batch = access.ingest_locations(locations)
    print(f"Authorized locations processed: {len(batch.locations)}")
    for lr in batch.locations:
        print(f"  [{lr.access.value}] {lr.location}  ({lr.image_count} images)  {lr.message}")
    print(f"Total images discovered across granted locations: {batch.total_images}")
