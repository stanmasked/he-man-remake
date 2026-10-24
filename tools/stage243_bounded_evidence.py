#!/usr/bin/env python3
"""Stage243 size-bounded reads for owner-private GPU evidence inputs.

Never read entire untrusted capture or log files before checking size.
These guards establish data-handling limits, not device/GPU provenance.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat


class EvidenceReadError(ValueError):
    pass


MAX_MANIFEST_BYTES = 64 * 1024
MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_RGBA_BYTES = 512
MAX_RECEIPT_BYTES = 256
MAX_PHASE_BYTES = 256
MAX_NONCE_BYTES = 64
MAX_EXIT_BYTES = 64
MAX_GUEST_EXIT_BYTES = 128


def _validate_limit(max_bytes: int) -> None:
    if not isinstance(max_bytes, int) or max_bytes < 1 or max_bytes > MAX_LOG_BYTES:
        raise EvidenceReadError("invalid bounded-read limit")


def _read_fd(fd: int, max_bytes: int, label: str) -> bytes:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        raise EvidenceReadError(f"{label}: expected a regular file")
    if info.st_size > max_bytes:
        raise EvidenceReadError(f"{label}: oversized ({info.st_size} > {max_bytes})")
    content = bytearray()
    while len(content) <= max_bytes:
        chunk = os.read(fd, min(64 * 1024, max_bytes + 1 - len(content)))
        if not chunk:
            break
        content.extend(chunk)
    if len(content) > max_bytes:
        raise EvidenceReadError(f"{label}: grew beyond {max_bytes} bytes")
    return bytes(content)


def read_limited_at(directory_fd: int, name: str, max_bytes: int, label: str) -> bytes:
    """Read a basename relative to a pinned directory descriptor without following links."""
    _validate_limit(max_bytes)
    if not isinstance(name, str) or not name or name in (".", "..") or Path(name).name != name:
        raise EvidenceReadError("descriptor-relative input must be a plain filename")
    if os.open not in getattr(os, "supports_dir_fd", set()):
        raise EvidenceReadError("descriptor-relative reads are unsupported on this platform")
    fd = None
    try:
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory_fd)
        result = _read_fd(fd, max_bytes, label)
        os.close(fd)
        fd = None
        return result
    except FileNotFoundError as exc:
        raise EvidenceReadError(f"{label}: missing file") from exc
    except OSError as exc:
        raise EvidenceReadError(f"{label}: cannot read regular file: {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)


def read_limited(path: Path, max_bytes: int, label: str) -> bytes:
    """Read at most max_bytes+1 even if the file changes after stat.

    On platforms with O_NOFOLLOW, reject symlinks in untrusted capture
    inputs; always require a regular file at the opened descriptor.
    """
    _validate_limit(max_bytes)
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        content = _read_fd(fd, max_bytes, label)
        os.close(fd)
        fd = None
        return content
    except FileNotFoundError as exc:
        raise EvidenceReadError(f"{label}: missing file") from exc
    except OSError as exc:
        raise EvidenceReadError(f"{label}: cannot read regular file: {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)
