#!/usr/bin/env python3
"""Stage247 Windows-only gated launch test using invented child processes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

from stage240_private_emulator_launcher import (
    WindowsJobObject, start_windows_gated_process, terminate_process_tree,
)


def run_case() -> dict:
    if os.name != "nt":
        raise RuntimeError("Stage247 gated launch matrix must run on Windows")
    with tempfile.TemporaryDirectory(prefix="heman-stage247-gated-") as temp:
        root = Path(temp)
        log = root / "host-output.log"
        # The target starts only after the wrapper has been assigned to the Job.
        # It then spawns a 60-second descendant inheriting stdout and exits 0.
        target_code = (
            "import subprocess,sys\n"
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
        )
        job = WindowsJobObject()
        state = {
            "captured_bytes": 0, "total_bytes": 0, "truncated": False,
            "error": None, "drain_incomplete": False,
            "windows_job_object_assigned": False,
        }
        proc = None
        reader = None
        try:
            proc, reader = start_windows_gated_process(
                [sys.executable, "-c", target_code], job, log, state)
            wrapper_exit_code = proc.wait(timeout=15)
            reader.join(timeout=2)
            pipe_open_after_wrapper_exit = reader.is_alive()
            active_before_cleanup = job.active_process_count()
            cleanup = terminate_process_tree(proc, grace_seconds=10, job=job)
            reader.join(timeout=10)
            drain_finished = not reader.is_alive()
            result = {
                "wrapper_exit_code": wrapper_exit_code,
                "job_assigned_before_target_started": state["windows_job_object_assigned"],
                "pipe_open_after_wrapper_exit": pipe_open_after_wrapper_exit,
                "active_processes_before_cleanup": active_before_cleanup,
                "cleanup_method": cleanup["method"],
                "cleanup_success": cleanup["success"],
                "job_closed": cleanup["job_closed"],
                "parent_reaped": cleanup["parent_reaped"],
                "drain_finished_after_cleanup": drain_finished,
                "log_size_bytes": log.stat().st_size if log.exists() else None,
                "gpu_execution_verified": False,
                "original_ios_parity_verified": False,
            }
            if not (
                wrapper_exit_code == 0
                and state["windows_job_object_assigned"] is True
                and pipe_open_after_wrapper_exit
                and active_before_cleanup >= 1
                and cleanup["method"] == "windows_job_object_kill_on_close"
                and cleanup["success"] is True and cleanup["job_closed"] is True
                and drain_finished
            ):
                raise RuntimeError("Stage247 gated Windows launch invariant failed: "
                                   + json.dumps(result, sort_keys=True))
            return result
        finally:
            if job.is_open:
                job.close()
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "schema": "heman-stage247-gated-windows-launch-v1",
        "result": "gated_windows_launch_process_tree_pass",
        "synthetic_only": True,
        "case": run_case(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("STAGE247_GATED_WINDOWS_LAUNCH_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
