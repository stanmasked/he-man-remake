#!/usr/bin/env python3
"""Stage250 integration matrix for the canonical Stage234 phase contract."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from analyze_stage235_gpu_capture import analyze
from collect_stage236_gpu_bundle import phase_info
from stage231_capture_session import payload
from stage234_phase_contract import PHASES, describe_phase


def build_report() -> dict:
    nonce = "a" * 32
    fixture = payload()
    rows = []
    for expected_index, phase in enumerate(PHASES, start=1):
        details = describe_phase(phase)
        phase_bytes = f"STAGE234_GPU_PHASE nonce={nonce} phase={phase}\n".encode("ascii")
        analyzer = analyze(fixture, None, phase_bytes)["phase"]
        bundle = phase_info(phase_bytes, nonce)
        assert details["known_phase"] is True
        assert details["phase_index"] == expected_index
        assert analyzer["phase_index"] == expected_index
        assert bundle["phase_index"] == expected_index
        assert analyzer["next_expected"] == details["next_expected"]
        assert bundle["next_expected"] == details["next_expected"]
        assert analyzer["runtime_gpu_execution_attested"] is False
        assert bundle["runtime_gpu_execution_attested"] is False
        assert details["original_ios_graphics_parity_attested"] is False
        rows.append({
            "phase_index": expected_index,
            "phase": phase,
            "milestone": details["milestone"],
            "next_expected": details["next_expected"],
            "progress_interpretation": details["progress_interpretation"],
            "analyzer_index": analyzer["phase_index"],
            "bundle_index": bundle["phase_index"],
            "runtime_gpu_execution_attested": False,
            "original_ios_graphics_parity_attested": False,
        })

    submitted = describe_phase("05_render_commands_submitted")
    queue_idle = describe_phase("06_render_queue_idle")
    final = describe_phase("07_receipt_committed")
    assert submitted["next_expected"] == "wait_for_render_queue_idle"
    assert queue_idle["next_expected"] == "cpu_readback_compare_and_commit_receipt"
    assert final["next_expected"] is None

    unknown_bytes = f"STAGE234_GPU_PHASE nonce={nonce} phase=99_future_phase\n".encode("ascii")
    unknown_analyzer = analyze(fixture, None, unknown_bytes)["phase"]
    unknown_bundle = phase_info(unknown_bytes, nonce)
    assert unknown_analyzer["syntax_valid"] is True
    assert unknown_analyzer["known_phase"] is False
    assert unknown_analyzer["phase_index"] is None
    assert unknown_bundle["known_phase"] is False
    assert unknown_bundle["phase_index"] is None
    return {
        "schema": "heman-stage250-phase-contract-v1",
        "result": "stage250_phase_contract_pass",
        "synthetic_only": True,
        "phase_count": len(PHASES),
        "phase_order": list(PHASES),
        "phases": rows,
        "unknown_phase_rejected_for_progress": True,
        "render_submit_and_queue_idle_are_distinct": True,
        "runtime_gpu_execution_attested": False,
        "original_ios_graphics_parity_attested": False,
        "note": "Canonical phase semantics and report ordering only; not runtime provenance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("STAGE250_PHASE_CONTRACT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
