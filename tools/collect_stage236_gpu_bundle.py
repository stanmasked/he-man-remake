#!/usr/bin/env python3
"""Stage236: bind private raw captures, phase, receipt, and NRO to one session.

This produces a diagnostic consistency report. It cannot independently attest
that a Switch/GPU-capable emulator actually executed the supplied NRO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from stage231_capture_session import nro_sha256, SessionError
from analyze_stage235_gpu_capture import analyze, DiagnosticError

NONCE = re.compile(r"[0-9a-f]{32}")
RECEIPT = re.compile(
    r"STAGE230_GPU_READBACK width=(\d+) height=(\d+) bytes=(\d+) "
    r"pixels=(\d+) mismatches=(\d+) nonce=([0-9a-f]{32})\n?"
)
PHASE = re.compile(
    rb"STAGE234_GPU_PHASE nonce=([0-9a-f]{32}) phase=([0-9a-z_]+)\n"
)
KNOWN_PHASES = {
    "01_nonce_validated", "02_shaders_loaded",
    "03_texture_upload_queue_idle", "04_upload_pixels_match",
    "05_render_queue_idle", "06_receipt_committed",
}
BYTE_COUNT = 512


class BundleError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path, label: str) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"{label}: cannot read valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise BundleError(f"{label}: expected JSON object")
    return obj


def describe_file(path: Path, expected_bytes: int | None = None) -> tuple[dict, bytes | None]:
    if not path.exists():
        return {"status": "missing"}, None
    if not path.is_file():
        return {"status": "not_a_regular_file"}, None
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"status": "read_error", "error": str(exc)}, None
    info = {"status": "present", "bytes": len(data), "sha256": sha(data)}
    if expected_bytes is not None:
        info["expected_bytes"] = expected_bytes
        info["size_valid"] = len(data) == expected_bytes
    return info, data


def receipt_info(data: bytes | None, session_nonce: str) -> dict:
    if data is None:
        return {"status": "missing_or_unreadable", "nonce_matches_session": None}
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        return {"status": "invalid_non_ascii", "nonce_matches_session": False}
    match = RECEIPT.fullmatch(text)
    if not match:
        return {"status": "invalid_format", "nonce_matches_session": False}
    width, height, size, pixels, mismatches, nonce = match.groups()
    dimensions = tuple(map(int, (width, height, size, pixels))) == (16, 8, 512, 128)
    nonce_matches = nonce == session_nonce
    return {
        "status": "valid" if dimensions and nonce_matches else "mismatch",
        "width": int(width), "height": int(height), "bytes": int(size),
        "pixels": int(pixels), "mismatches": int(mismatches),
        "nonce_matches_session": nonce_matches,
        "dimensions_valid": dimensions,
        "zero_pixel_mismatches": int(mismatches) == 0,
        "sha256": sha(data),
    }


def phase_info(data: bytes | None, session_nonce: str) -> dict:
    if data is None:
        return {"status": "missing_or_unreadable", "nonce_matches_session": None}
    if len(data) > 256:
        return {"status": "oversized", "nonce_matches_session": False}
    match = PHASE.fullmatch(data)
    if not match:
        return {"status": "invalid_format", "nonce_matches_session": False,
                "sha256": sha(data)}
    nonce = match[1].decode("ascii")
    phase = match[2].decode("ascii")
    nonce_matches = nonce == session_nonce
    known = phase in KNOWN_PHASES
    return {
        "status": "valid" if nonce_matches and known else "mismatch",
        "phase": phase,
        "phase_index": sorted(KNOWN_PHASES).index(phase) + 1 if known else None,
        "nonce_matches_session": nonce_matches,
        "known_phase": known,
        "sha256": sha(data),
        "note": "CPU-side checkpoint only; not GPU execution attestation",
    }


def collect_bundle(nro: Path, sd_root: Path, session_dir: Path) -> dict:
    session_path = session_dir / "stage231_session.json"
    session = read_json(session_path, "Stage231 session")
    if session.get("schema") != "stage231-capture-session-v1":
        raise BundleError("unexpected Stage231 session schema")
    nonce = session.get("nonce")
    if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
        raise BundleError("invalid Stage231 session nonce")
    try:
        current_nro_sha = nro_sha256(nro)
    except (SessionError, OSError) as exc:
        raise BundleError(f"invalid NRO: {exc}") from exc
    nro_matches = session.get("nro_sha256") == current_nro_sha

    sd_dir = sd_root / "switch" / "heman-stage230"
    file_specs = {
        "upload": (sd_dir / "upload.rgba", BYTE_COUNT),
        "render": (sd_dir / "readback.rgba", BYTE_COUNT),
        "phase": (sd_dir / "gpu_phase.txt", None),
        "receipt": (sd_dir / "readback.receipt", None),
        "sd_nonce": (sd_dir / "run_nonce.txt", None),
    }
    files = {}
    raw = {}
    for label, (path, expected_bytes) in file_specs.items():
        info, data = describe_file(path, expected_bytes)
        files[label] = info
        raw[label] = data

    sd_nonce_data = raw["sd_nonce"]
    if sd_nonce_data is None:
        sd_nonce_matches = None
    else:
        sd_nonce_matches = sd_nonce_data == (nonce + "\n").encode("ascii")
    phase = phase_info(raw["phase"], nonce)
    receipt = receipt_info(raw["receipt"], nonce)

    collected_path = session_dir / "stage231_collected.json"
    collected = None
    if collected_path.is_file():
        try:
            candidate = read_json(collected_path, "Stage231 collected report")
            result_matches = candidate.get("result") == "submitted_capture_matches_challenge_and_pixels"
            collected_render_matches = bool(
                raw["render"] is not None
                and files["render"].get("size_valid")
                and candidate.get("rgba_sha256") == sha(raw["render"])
            )
            collected_ok = (
                candidate.get("schema") == "stage231-collected-synthetic-gpu-evidence-v1"
                and candidate.get("nonce") == nonce
                and candidate.get("nro_sha256") == current_nro_sha
                and result_matches
                and collected_render_matches
                and candidate.get("runtime_provenance_attested") is False
            )
            collected = {
                "status": "valid" if collected_ok else "mismatch",
                "nonce_matches_session": candidate.get("nonce") == nonce,
                "nro_matches": candidate.get("nro_sha256") == current_nro_sha,
                "result_matches": result_matches,
                "render_hash_matches": collected_render_matches,
                "runtime_provenance_attested": candidate.get("runtime_provenance_attested"),
            }
        except BundleError as exc:
            collected = {"status": "invalid", "error": str(exc)}
    else:
        collected = {"status": "missing"}

    upload = raw["upload"] if files["upload"].get("size_valid") else None
    render = raw["render"] if files["render"].get("size_valid") else None
    if upload is not None or render is not None:
        phase_for_diagnostics = raw["phase"]
        if phase_for_diagnostics is not None and len(phase_for_diagnostics) > 256:
            phase_for_diagnostics = None
        diagnostics = analyze(upload, render, phase_for_diagnostics)
    else:
        diagnostics = None

    both_captures_match = bool(
        diagnostics is not None
        and diagnostics.get("captures", {}).get("upload", {}).get("matches_fixture_exactly")
        and diagnostics.get("captures", {}).get("render", {}).get("matches_fixture_exactly")
    )
    phase_final = phase.get("phase") == "06_receipt_committed"
    receipt_clean = bool(
        receipt.get("status") == "valid"
        and receipt.get("mismatches") == 0
        and receipt.get("nonce_matches_session") is True
    )
    all_session_links = bool(
        nro_matches and sd_nonce_matches is True
        and phase.get("nonce_matches_session") is True
        and receipt.get("nonce_matches_session") is True
    )
    consistent = bool(all_session_links and phase_final and receipt_clean and both_captures_match)

    return {
        "schema": "stage236-private-capture-bundle-v1",
        "session": {
            "nonce": nonce,
            "prepared_nro_sha256": session.get("nro_sha256"),
            "observed_nro_sha256": current_nro_sha,
            "nro_matches_prepared_session": nro_matches,
        },
        "files": files,
        "session_links": {
            "sd_nonce_matches_session": sd_nonce_matches,
            "phase_nonce_matches_session": phase.get("nonce_matches_session"),
            "receipt_nonce_matches_session": receipt.get("nonce_matches_session"),
            "all_session_links_match": all_session_links,
        },
        "phase": phase,
        "receipt": receipt,
        "stage231_collected_report": collected,
        "pixel_diagnostics": diagnostics,
        "consistency_gate": {
            "phase_final_receipt_committed": phase_final,
            "receipt_reports_zero_mismatches": receipt_clean,
            "both_upload_and_render_match_synthetic_fixture": both_captures_match,
            "synthetic_bundle_consistent": consistent,
            "runtime_gpu_execution_attested": False,
            "original_ios_graphics_parity_attested": False,
            "note": "Consistency checks do not authenticate hardware/emulator provenance.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nro", type=Path, required=True)
    parser.add_argument("--sd-root", type=Path, required=True)
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="write the report to a private Evidence Archive path")
    parser.add_argument("--require-complete", action="store_true",
                        help="exit 2 unless the synthetic consistency gate passes")
    args = parser.parse_args()
    try:
        report = collect_bundle(args.nro, args.sd_root, args.session_dir)
    except (BundleError, OSError, DiagnosticError) as exc:
        print(f"STAGE236_FAIL: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, sort_keys=True, indent=2) + "\n"
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    except OSError as exc:
        print(f"STAGE236_FAIL: cannot preserve report: {exc}", file=sys.stderr)
        return 1
    print(text, end="")
    if args.require_complete and not report["consistency_gate"]["synthetic_bundle_consistent"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
