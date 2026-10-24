#!/usr/bin/env python3
"""Stage241: check a nonce-bound guest-written NRO exit receipt.

This parses a guest-controlled CPU file, not independent proof of emulated
GPU execution. Host process exit and guest exit are deliberately distinct.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re

RECEIPT=re.compile(rb"STAGE241_GUEST_EXIT nonce=([0-9a-f]{32}) code=(0|[1-9][0-9]{0,2})\n")
NONCE=re.compile(r"[0-9a-f]{32}")
MAX_BYTES=128


def check_guest_exit(raw: bytes | None, expected_nonce: str) -> dict:
    if not isinstance(expected_nonce,str) or not NONCE.fullmatch(expected_nonce):
        raise ValueError("expected nonce must be 32 lowercase hexadecimal characters")
    if raw is None:
        return {
            "status":"missing",
            "guest_exit_code":None,
            "nonce_matches_session":False,
            "guest_reported_success":False,
            "runtime_gpu_execution_attested":False,
        }
    if type(raw) is not bytes or len(raw)>MAX_BYTES:
        return {
            "status":"oversized_or_unreadable",
            "guest_exit_code":None,
            "nonce_matches_session":False,
            "guest_reported_success":False,
            "runtime_gpu_execution_attested":False,
        }
    common={
        "bytes":len(raw),
        "sha256":hashlib.sha256(raw).hexdigest(),
        "runtime_gpu_execution_attested":False,
    }
    match=RECEIPT.fullmatch(raw)
    if not match:
        return dict(common,status="malformed",guest_exit_code=None,
                    nonce_matches_session=False,guest_reported_success=False)
    code=int(match[2])
    same=match[1].decode("ascii")==expected_nonce
    return dict(common,
                status="valid" if same else "nonce_mismatch",
                guest_exit_code=code,
                nonce_matches_session=same,
                guest_reported_success=same and code==0)


def inspect_guest_exit_file(path: Path, expected_nonce: str) -> dict:
    if not path.exists() or not path.is_file():
        return check_guest_exit(None,expected_nonce)
    try:
        if path.stat().st_size>MAX_BYTES:
            return check_guest_exit(b"x"*(MAX_BYTES+1),expected_nonce)
        return check_guest_exit(path.read_bytes(),expected_nonce)
    except OSError:
        return check_guest_exit(None,expected_nonce)
