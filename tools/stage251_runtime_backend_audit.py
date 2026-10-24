#!/usr/bin/env python3
"""Stage251: classify emulator log backend claims without asserting GPU provenance.

The parser reads bounded, caller-supplied logs. A graphics API name is only a
log claim: Vulkan/OpenGL may still use software rendering, and log text can be
fabricated. This tool never sets a GPU execution attestation to true.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

MAX_LOG_BYTES = 4 * 1024 * 1024

BACKEND_PATTERNS = {
    "vulkan": re.compile(
        r"\b(?:gpu|graphics|renderer)\s+(?:backend|api)\s*[:=]\s*vulkan\b",
        re.IGNORECASE,
    ),
    "opengl": re.compile(
        r"\b(?:gpu|graphics|renderer)\s+(?:backend|api)\s*[:=]\s*opengl\b",
        re.IGNORECASE,
    ),
    "direct3d11": re.compile(
        r"\b(?:gpu|graphics|renderer)\s+(?:backend|api)\s*[:=]\s*(?:direct3d\s*11|d3d11)\b",
        re.IGNORECASE,
    ),
    "direct3d12": re.compile(
        r"\b(?:gpu|graphics|renderer)\s+(?:backend|api)\s*[:=]\s*(?:direct3d\s*12|d3d12)\b",
        re.IGNORECASE,
    ),
    "metal": re.compile(
        r"\b(?:gpu|graphics|renderer)\s+(?:backend|api)\s*[:=]\s*metal\b",
        re.IGNORECASE,
    ),
}

SOFTWARE_PATTERNS = {
    "llvmpipe": re.compile(r"\bllvmpipe\b", re.IGNORECASE),
    "lavapipe": re.compile(r"\blavapipe\b", re.IGNORECASE),
    "swiftshader": re.compile(r"\bswiftshader\b", re.IGNORECASE),
    "softpipe": re.compile(r"\bsoftpipe\b", re.IGNORECASE),
    "swrast": re.compile(r"\bswrast\b", re.IGNORECASE),
    "software_renderer": re.compile(
        r"\bsoftware\s+(?:renderer|rasterizer)\b|\brenderer\s*[:=]\s*software\b",
        re.IGNORECASE,
    ),
    "software_backend": re.compile(
        r"\b(?:gpu|graphics|renderer)\s+(?:backend|api)\s*[:=]\s*(?:software|cpu)\b",
        re.IGNORECASE,
    ),
}


class AuditError(ValueError):
    """Input cannot be safely audited."""


def analyze_bytes(data: bytes, source_name: str = "<bytes>") -> dict:
    if not isinstance(data, bytes):
        raise AuditError("log content must be bytes")
    if len(data) > MAX_LOG_BYTES:
        raise AuditError(f"log exceeds {MAX_LOG_BYTES} bytes")
    text = data.decode("utf-8", errors="replace")
    backend_lines = {name: [] for name in BACKEND_PATTERNS}
    software_lines = {name: [] for name in SOFTWARE_PATTERNS}

    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in BACKEND_PATTERNS.items():
            if pattern.search(line):
                backend_lines[name].append(line_number)
        for name, pattern in SOFTWARE_PATTERNS.items():
            if pattern.search(line):
                software_lines[name].append(line_number)

    backends = [name for name, lines in backend_lines.items() if lines]
    software_indicators = [
        name for name, lines in software_lines.items() if lines
    ]
    if software_indicators:
        classification = "software_rendering_indicator_found"
    elif len(backends) == 1:
        classification = "graphics_api_reported_no_software_marker"
    elif len(backends) > 1:
        classification = "multiple_or_conflicting_graphics_apis"
    else:
        classification = "no_recognized_backend_evidence"

    return {
        "schema": "heman-stage251-runtime-backend-audit-v1",
        "result": "stage251_runtime_backend_audit_complete",
        "source_name": source_name,
        "log_bytes": len(data),
        "log_sha256": hashlib.sha256(data).hexdigest(),
        "classification": classification,
        "reported_backends": backends,
        "backend_evidence_line_numbers": {
            name: lines for name, lines in backend_lines.items() if lines
        },
        "software_indicators": software_indicators,
        "software_indicator_line_numbers": {
            name: lines for name, lines in software_lines.items() if lines
        },
        "api_reported_without_software_marker": (
            len(backends) == 1 and not software_indicators
        ),
        "gpu_capability_independently_verified": False,
        "runtime_gpu_execution_attested": False,
        "original_ios_graphics_parity_attested": False,
        "note": (
            "Log claims are diagnostic only. API names do not prove a physical "
            "GPU, hardware acceleration, genuine guest execution, or iOS parity."
        ),
    }


def analyze_file(path: Path) -> dict:
    if not path.is_absolute():
        raise AuditError("log path must be absolute")
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise AuditError(f"cannot stat log: {type(exc).__name__}: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise AuditError("log must not be a symbolic link")
    if not stat.S_ISREG(metadata.st_mode):
        raise AuditError("log must be a regular file")
    if metadata.st_size > MAX_LOG_BYTES:
        raise AuditError(f"log exceeds {MAX_LOG_BYTES} bytes")
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_LOG_BYTES + 1)
    except OSError as exc:
        raise AuditError(f"cannot read log: {type(exc).__name__}: {exc}") from exc
    if len(data) > MAX_LOG_BYTES:
        raise AuditError(f"log exceeds {MAX_LOG_BYTES} bytes")
    return analyze_bytes(data, path.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True,
                        help="absolute path to the emulator's own runtime log")
    parser.add_argument("--output", type=Path,
                        help="optional JSON report path; keep real reports private")
    args = parser.parse_args()
    try:
        report = analyze_file(args.log)
        serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            if args.output.is_symlink():
                raise AuditError("output report must not be a symbolic link")
            args.output.write_text(serialized, encoding="utf-8")
    except (AuditError, OSError) as exc:
        print(f"STAGE251_FAIL: {exc}", file=sys.stderr)
        return 1
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
