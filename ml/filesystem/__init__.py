"""ChatLens local filesystem access (user-authorized locations).

This package's ONLY job is to take filesystem location(s) that the user has
authorized and hand them to the EXISTING ingestion scanner. It does not scan,
OCR, embed, index, or retrieve anything itself, and it does not modify any ML
component.
"""
from .local_access import (
    LocalImageAccess,
    OperatingSystem,
    AccessResult,
    LocationResult,
    detect_os,
)

__all__ = [
    "LocalImageAccess",
    "OperatingSystem",
    "AccessResult",
    "LocationResult",
    "detect_os",
]
