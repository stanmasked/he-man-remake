#!/usr/bin/env python3
"""Stage248 Windows-only tests for gated launcher exit-code and failure contract."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from stage240_private_emulator_launcher import (
    WindowsJobObject, start_windows_gated_process,
)


def run_case(command: list[str], expected_code: int, marker: bytes | None) -> dict:
    with tempfile.TemporaryDirectory(prefix="heman-stage248-exit-") as temp:
        root = Path(temp)
        log = root / "host-output.log"
        job = WindowsJobObject()
        state = {
            "captured_bytes": 0, "total_bytes": 0, "truncated": False,
            "error": None, "drain_incomplete": False,
            "windows_job_object_assigned": False,
        }
        proc = None
        reader = None
        try:
            proc, reader = start_windows_gated_process(command, job, log, state)
            code = proc.wait(timeout=15)
            reader.join(timeout=5)
            drained = not reader.is_alive()
            active = job.active_process_count()
            log_bytes = log.read_bytes() if log.exists() else b""
            closed = job.close()
            result = {
                "exit_code": code,
                "expected_exit_code": expected_code,
                "job_assigned_before_target_started": state["windows_job_object_assigned"],
                "active_processes_after_exit": active,
                "job_closed": closed,
                "output_drain_finished": drained,
                "log_bytes": len(log_bytes),
                "marker_seen": marker is None or marker in log_bytes,
            }
            if not (
                code == expected_code
                and state["windows_job_object_assigned"] is True
                and active == 0 and closed is True and drained
                and result["marker_seen"]
            ):
                raise RuntimeError("Stage248 exit contract failed: "
                                   + json.dumps(result, sort_keys=True))
            return result
        finally:
            if job.is_open:
                job.close()
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
            if reader is not None:
                reader.join(timeout=2)


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("Stage248 exit-contract matrix must run on Windows")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    success_marker = b"STAGE248_CHILD_EXIT_7"
    success_code = run_case(
        [sys.executable, "-c",
         "import sys; print('STAGE248_CHILD_EXIT_7', flush=True); sys.exit(7)"],
        7, success_marker)
    # Simulate the executable disappearing after initial path validation.
    failure_code = run_case(
        [str(Path(tempfile.gettempdir()) / "heman-stage248-missing-emulator.exe")],
        127, b"STAGE247_GATED_LAUNCH_FAIL")
    report = {
        "schema": "heman-stage248-windows-exit-contract-v1",
        "result": "windows_gated_exit_contract_pass",
        "synthetic_only": True,
        "exit_code_propagation": success_code,
        "child_launch_failure": failure_code,
        "gpu_execution_verified": False,
        "original_ios_parity_verified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("STAGE248_WINDOWS_EXIT_CONTRACT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
