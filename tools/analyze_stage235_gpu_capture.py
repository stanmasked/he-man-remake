#!/usr/bin/env python3
"""Stage235: diagnose synthetic GPU upload/render readback mismatches.

This tool compares submitted raw bytes against an invented 16x8 RGBA fixture.
It can identify exact spatial/channel transformations and summarize mismatches.
It does not authenticate the runtime, device, or GPU execution.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

from stage231_capture_session import payload
from stage234_phase_contract import describe_phase

WIDTH, HEIGHT, CHANNELS = 16, 8, 4
BYTE_COUNT = WIDTH * HEIGHT * CHANNELS
CHANNELS_NAME = "RGBA"
PHASE_RE = re.compile(
    rb"STAGE234_GPU_PHASE nonce=([0-9a-f]{32}) phase=([0-9a-z_]+)\n"
)


class DiagnosticError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_capture(data: bytes, label: str) -> bytes:
    if type(data) is not bytes:
        raise DiagnosticError(f"{label}: expected raw bytes")
    if len(data) != BYTE_COUNT:
        raise DiagnosticError(
            f"{label}: expected exactly {BYTE_COUNT} bytes, got {len(data)}"
        )
    return data


def diff_stats(actual: bytes, expected: bytes) -> dict:
    validate_capture(actual, "actual")
    validate_capture(expected, "expected")
    byte_diffs = [i for i, (a, e) in enumerate(zip(actual, expected)) if a != e]
    pixel_diffs = []
    row_counts = []
    for y in range(HEIGHT):
        count = 0
        for x in range(WIDTH):
            p = (y * WIDTH + x) * CHANNELS
            if actual[p:p+CHANNELS] != expected[p:p+CHANNELS]:
                pixel_diffs.append((x, y))
                count += 1
        row_counts.append(count)
    first = []
    for x, y in pixel_diffs[:8]:
        p = (y * WIDTH + x) * CHANNELS
        first.append({
            "x": x, "y": y,
            "expected_rgba": expected[p:p+4].hex(),
            "actual_rgba": actual[p:p+4].hex(),
        })
    return {
        "mismatched_bytes": len(byte_diffs),
        "mismatched_pixels": len(pixel_diffs),
        "first_mismatches": first,
        "row_mismatch_pixels": row_counts,
    }


def transform_expected(expected: bytes, flip_x: bool, flip_y: bool,
                       channel_order: tuple[int, int, int, int]) -> bytes:
    validate_capture(expected, "expected")
    out = bytearray(BYTE_COUNT)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            sx = WIDTH - 1 - x if flip_x else x
            sy = HEIGHT - 1 - y if flip_y else y
            src = (sy * WIDTH + sx) * CHANNELS
            dst = (y * WIDTH + x) * CHANNELS
            for channel in range(CHANNELS):
                out[dst + channel] = expected[src + channel_order[channel]]
    return bytes(out)


def transform_name(flip_x: bool, flip_y: bool,
                   channel_order: tuple[int, int, int, int]) -> str:
    parts = []
    if flip_x:
        parts.append("flip_x")
    if flip_y:
        parts.append("flip_y")
    if channel_order != (0, 1, 2, 3):
        parts.append("channels_" + "".join(CHANNELS_NAME[i] for i in channel_order))
    return "+".join(parts) if parts else "identity"


def classify(actual: bytes, expected: bytes) -> dict:
    validate_capture(actual, "actual")
    validate_capture(expected, "expected")
    ranked = []
    exact = []
    for flip_x, flip_y in itertools.product((False, True), repeat=2):
        for order in itertools.permutations(range(CHANNELS)):
            candidate = transform_expected(expected, flip_x, flip_y, order)
            stats = diff_stats(actual, candidate)
            name = transform_name(flip_x, flip_y, order)
            entry = {
                "transform": name,
                "mismatched_pixels": stats["mismatched_pixels"],
                "mismatched_bytes": stats["mismatched_bytes"],
            }
            if stats["mismatched_bytes"] == 0:
                exact.append(name)
            ranked.append((stats["mismatched_pixels"], stats["mismatched_bytes"], name, entry))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return {
        "exact_candidate_transforms": exact,
        "best_candidate_transforms": [] if exact else [row[3] for row in ranked[:3]],
        "candidate_space": "4 spatial orientations x 24 RGBA channel permutations",
    }


def analyze(upload: bytes | None, render: bytes | None,
            phase_bytes: bytes | None = None) -> dict:
    if upload is None and render is None:
        raise DiagnosticError("provide at least one of upload or render capture")
    expected = payload()
    report = {
        "schema": "stage235-synthetic-gpu-capture-diagnostics-v1",
        "fixture": {
            "width": WIDTH, "height": HEIGHT, "channels": CHANNELS_NAME,
            "bytes": BYTE_COUNT, "sha256": sha(expected),
            "source": "invented Stage231 16x8 RGBA fixture",
        },
        "evidence_boundary": {
            "runtime_gpu_execution_attested": False,
            "original_ios_graphics_parity_attested": False,
            "note": "Byte analysis and phase strings do not authenticate GPU execution.",
        },
        "captures": {},
    }
    if phase_bytes is not None:
        if len(phase_bytes) > 256:
            raise DiagnosticError("phase file exceeds 256 bytes")
        m = PHASE_RE.fullmatch(phase_bytes)
        phase_name = m[2].decode("ascii") if m else ""
        progress = describe_phase(phase_name)
        report["phase"] = {
            **progress,
            "sha256": sha(phase_bytes),
            "syntax_valid": bool(m),
            "phase": phase_name if m else None,
            "nonce": m[1].decode("ascii") if m else None,
            "interpretation": "untrusted CPU checkpoint; not GPU attestation",
        }
    for label, data in (("upload", upload), ("render", render)):
        if data is None:
            continue
        validate_capture(data, label)
        stats = diff_stats(data, expected)
        report["captures"][label] = {
            "sha256": sha(data),
            "matches_fixture_exactly": stats["mismatched_bytes"] == 0,
            "fixture_diff": stats,
            "transform_analysis": classify(data, expected),
        }
    if upload is not None and render is not None:
        report["upload_vs_render"] = {
            "sha256_upload": sha(upload),
            "sha256_render": sha(render),
            **diff_stats(render, upload),
            "byte_identical": upload == render,
        }
        upload_ok = upload == expected
        render_ok = render == expected
        if upload_ok and render_ok:
            hint = "both_captures_match_fixture"
        elif upload_ok and not render_ok:
            hint = "upload_matches_fixture_divergence_appears_after_upload_path"
        elif not upload_ok and upload == render:
            hint = "both_captures_share_same_deviation_investigate_transfer_before_sampler"
        elif not upload_ok and not render_ok:
            hint = "both_captures_deviate_compare_transform_and_per_row_diagnostics"
        else:
            hint = "captures_differ_review_upload_and_draw_paths"
        report["triage_hint"] = hint
    elif upload is not None:
        report["triage_hint"] = (
            "upload_matches_fixture" if upload == expected
            else "upload_capture_deviates_review_transfer_stage"
        )
    else:
        report["triage_hint"] = (
            "render_matches_fixture" if render == expected
            else "render_capture_deviates_review_shader_raster_and_readback"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", type=Path, help="private 512-byte upload.rgba")
    parser.add_argument("--render", type=Path, help="private 512-byte readback.rgba")
    parser.add_argument("--phase", type=Path, help="optional private gpu_phase.txt")
    parser.add_argument("--output", type=Path, help="write report to private path")
    args = parser.parse_args()
    try:
        upload = args.upload.read_bytes() if args.upload else None
        render = args.render.read_bytes() if args.render else None
        phase = args.phase.read_bytes() if args.phase else None
        report = analyze(upload, render, phase)
    except (OSError, DiagnosticError) as exc:
        print(f"STAGE235_FAIL: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
