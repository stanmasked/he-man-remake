#!/usr/bin/env python3
"""Fail-closed Stage229 submitted GPU readback verifier (synthetic 16x8 only).

A passing report validates bytes/provenance *claims* supplied by the caller.
It does not attest that a Switch GPU or emulator really executed the NRO.
Never run against private game art or publish owner-only runtime logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

WIDTH = 16
HEIGHT = 8
BYTES = WIDTH * HEIGHT * 4
BEGIN = re.compile(r"^STAGE229_GPU_READBACK_BEGIN width=(\d+) height=(\d+) bytes=(\d+)$")
ROW = re.compile(r"^STAGE229_GPU_READBACK_ROW y=(\d+) rgba=([0-9a-f]+)$")
END = re.compile(r"^STAGE229_GPU_READBACK_END mismatches=(\d+)$")
OLD = re.compile(r"^STAGE228_GPU_QUAD_READBACK pixels=(\d+) mismatches=(\d+)$")
SHA = re.compile(r"[0-9a-f]{64}")


class EvidenceError(ValueError):
    """Incomplete, malformed, or uncorroborated evidence."""


def expected_pixels() -> bytes:
    out = bytearray()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if x < 9 and y < 5:
                out.extend((x * 20, y * 30, x + y, 255))
            else:
                out.extend((0, 0, 0, 255))
    assert len(out) == BYTES
    return bytes(out)


def _exactly_one(lines: list[str], regex: re.Pattern[str], name: str) -> tuple[int, re.Match[str]]:
    items = [(i, regex.fullmatch(line)) for i, line in enumerate(lines)]
    found = [(i, match) for i, match in items if match is not None]
    if len(found) != 1:
        raise EvidenceError(f"required exactly one {name}; found {len(found)}")
    return found[0]


def verify_capture(log: str, exit_code: int, nro: bytes, metadata: dict) -> dict:
    if not isinstance(log, str) or len(log.encode("utf-8")) > 65536:
        raise EvidenceError("runtime log absent or exceeds 64 KiB")
    if exit_code != 0:
        raise EvidenceError(f"nonzero runtime exit: {exit_code}")
    if not isinstance(nro, bytes) or len(nro) < 20 or nro[16:20] != b"NRO0":
        raise EvidenceError("missing or malformed actual NRO")
    if not isinstance(metadata, dict):
        raise EvidenceError("runtime metadata must be JSON object")
    if metadata.get("schema") != "stage229-gpu-run-v1":
        raise EvidenceError("invalid evidence schema")
    if metadata.get("source_kind") != "real_runtime":
        raise EvidenceError("synthetic or source-build input is not runtime evidence")
    if metadata.get("runtime") not in ("switch_hardware", "gpu_capable_emulator"):
        raise EvidenceError("CPU-only or unspecified runtime is disallowed")
    if metadata.get("gpu_execution_observed") is not True or metadata.get("stdout_captured") is not True:
        raise EvidenceError("missing declared runtime observation")
    if type(metadata.get("runner_exit_code")) is not int or metadata["runner_exit_code"] != 0:
        raise EvidenceError("missing independent zero-exit receipt")
    if not isinstance(metadata.get("command"), str) or not metadata["command"].strip():
        raise EvidenceError("missing actual execution command")
    expected_digest = hashlib.sha256(nro).hexdigest()
    if metadata.get("nro_sha256") != expected_digest or not SHA.fullmatch(str(metadata.get("nro_sha256"))):
        raise EvidenceError("NRO hash mismatch")
    lines = log.splitlines()
    bpos, begin = _exactly_one(lines, BEGIN, "BEGIN")
    epos, end = _exactly_one(lines, END, "END")
    opos, old = _exactly_one(lines, OLD, "Stage228 result")
    if (int(begin[1]), int(begin[2]), int(begin[3])) != (WIDTH, HEIGHT, BYTES):
        raise EvidenceError("unexpected render dimensions")
    if not (bpos < epos < opos):
        raise EvidenceError("out-of-order runtime markers")
    if int(end[1]) or (int(old[1]), int(old[2])) != (WIDTH * HEIGHT, 0):
        raise EvidenceError("guest self-check recorded pixel mismatches")
    rows = [(i, m) for i, line in enumerate(lines)
            if (m := ROW.fullmatch(line)) is not None]
    if len(rows) != HEIGHT:
        raise EvidenceError(f"expected {HEIGHT} full rows; got {len(rows)}")
    if [i for i, _ in rows] != list(range(bpos + 1, epos)):
        raise EvidenceError("rows not contiguous or extra output in capture region")
    pixels = bytearray()
    for expected_y, (_, match) in enumerate(rows):
        if int(match[1]) != expected_y:
            raise EvidenceError("missing/reordered/duplicated row")
        hex_row = match[2]
        if len(hex_row) != WIDTH * 4 * 2:
            raise EvidenceError("invalid row byte count")
        pixels.extend(bytes.fromhex(hex_row))
    if len(pixels) != BYTES:
        raise EvidenceError("not enough readback pixels")
    expected = expected_pixels()
    if pixels != expected:
        first_byte = next(i for i, (actual, want) in enumerate(zip(pixels, expected)) if actual != want)
        raise EvidenceError(f"readback differs from C99 fixture at pixel {first_byte // 4} "
                            f"channel {first_byte % 4}")
    return {
        "schema": "stage229-validated-pixels-v1",
        "result": "submitted_capture_pixels_match",
        "pixel_count": WIDTH * HEIGHT,
        "byte_count": BYTES,
        "rgba_sha256": hashlib.sha256(pixels).hexdigest(),
        "nro_sha256": expected_digest,
        "submitted_runtime_kind": metadata["runtime"],
        "hardware_execution_independently_attested": False,
        "caution": "Capture contents and metadata can be fabricated; confirm real run provenance independently.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("exit_status", type=Path)
    parser.add_argument("nro", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--output", type=Path, help="optional derived report path")
    args = parser.parse_args()
    try:
        log = args.log.read_text(encoding="utf-8")
        exit_str = args.exit_status.read_text(encoding="ascii").strip()
        if not re.fullmatch(r"[0-9]{1,3}", exit_str):
            raise EvidenceError("invalid recorded exit code")
        nro = args.nro.read_bytes()
        if len(nro) > 16 * 1024 * 1024:
            raise EvidenceError("NRO exceeds bounded verification limit")
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        report = verify_capture(log, int(exit_str), nro, metadata)
    except (EvidenceError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"STAGE229_FAIL: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
