#!/usr/bin/env python3
"""Verify a submitted Stage230 SD capture. NEVER attest GPU provenance from bytes alone."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

WIDTH, HEIGHT = 16, 8
PIXEL_BYTES = WIDTH * HEIGHT * 4
RECEIPT = re.compile(
    r"STAGE230_GPU_READBACK width=(\d+) height=(\d+) bytes=(\d+) pixels=(\d+) mismatches=(\d+)\n?"
)
DIGEST = re.compile(r"[0-9a-f]{64}")


class CaptureError(ValueError):
    pass


def fixture() -> bytes:
    result = bytearray()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            result.extend((x * 20, y * 30, x + y, 255) if x < 9 and y < 5
                          else (0, 0, 0, 255))
    return bytes(result)


def check(data: bytes, receipt: str, nro: bytes,
          metadata: dict, exit_code: int) -> dict:
    if len(data) != PIXEL_BYTES:
        raise CaptureError("readback must have exactly 512 bytes")
    if not isinstance(receipt, str) or len(receipt) > 256:
        raise CaptureError("receipt absent/too long")
    m = RECEIPT.fullmatch(receipt)
    if not m:
        raise CaptureError("receipt missing, stale format or corrupt")
    if tuple(map(int, m.groups())) != (WIDTH, HEIGHT, PIXEL_BYTES, WIDTH * HEIGHT, 0):
        raise CaptureError("guest reported wrong dimensions or pixel mismatches")
    if data != fixture():
        idx = next(i for i, (a, b) in enumerate(zip(data, fixture())) if a != b)
        raise CaptureError(f"wrong RGBA byte at pixel {idx // 4} channel {idx % 4}")
    if len(nro) < 20 or len(nro) > 16 * 1024 * 1024 or nro[16:20] != b"NRO0":
        raise CaptureError("missing or malformed NRO")
    actual_sha = hashlib.sha256(nro).hexdigest()
    if not isinstance(metadata, dict):
        raise CaptureError("metadata must be JSON object")
    if metadata.get("schema") != "stage230-sd-capture-v1":
        raise CaptureError("unsupported capture schema")
    if metadata.get("source_kind") != "real_runtime":
        raise CaptureError("synthetic capture is not a runtime result")
    if metadata.get("runtime") not in ("switch_hardware", "gpu_capable_emulator"):
        raise CaptureError("CPU-only/unknown runtime")
    if metadata.get("gpu_execution_observed") is not True:
        raise CaptureError("no declared GPU observation")
    if not isinstance(metadata.get("command"), str) or not metadata["command"].strip():
        raise CaptureError("missing runner command")
    if metadata.get("nro_sha256") != actual_sha or not DIGEST.fullmatch(str(metadata.get("nro_sha256"))):
        raise CaptureError("executed NRO mismatch")
    if type(exit_code) is not int or exit_code != 0 or type(metadata.get("runner_exit_code")) is not int or metadata["runner_exit_code"] != 0:
        raise CaptureError("missing independent zero-exit record")
    return {
        "schema": "stage230-validated-sd-capture-v1",
        "status": "submitted_sd_capture_bytes_match",
        "rgba_sha256": hashlib.sha256(data).hexdigest(),
        "nro_sha256": actual_sha,
        "pixels": WIDTH * HEIGHT,
        "bytes": PIXEL_BYTES,
        "submitted_runtime_kind": metadata["runtime"],
        "hardware_execution_independently_attested": False,
        "caution": "Matching bytes and submitted metadata do not independently prove deko3d GPU execution.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rgba", type=Path)
    p.add_argument("receipt", type=Path)
    p.add_argument("nro", type=Path)
    p.add_argument("runtime_metadata", type=Path)
    p.add_argument("exit_status", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    try:
        if a.rgba.stat().st_size > PIXEL_BYTES:
            raise CaptureError("oversized readback")
        if a.nro.stat().st_size > 16 * 1024 * 1024:
            raise CaptureError("oversized NRO")
        exit_text = a.exit_status.read_text(encoding="ascii").strip()
        if not re.fullmatch(r"[0-9]{1,3}", exit_text):
            raise CaptureError("invalid runner exit receipt")
        result = check(a.rgba.read_bytes(), a.receipt.read_text(encoding="ascii"),
                       a.nro.read_bytes(),
                       json.loads(a.runtime_metadata.read_text(encoding="utf-8")),
                       int(exit_text))
    except (CaptureError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print("STAGE230_FAIL:", error, file=sys.stderr)
        return 1
    body = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if a.output:
        a.output.write_text(body, encoding="utf-8")
    print(body, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
