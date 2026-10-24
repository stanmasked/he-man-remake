#!/usr/bin/env python3
"""Stage246 Windows-only Job Object test using invented child processes."""
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
    WindowsJobObject, drain_bounded_output, terminate_process_tree,
)


def run_case() -> dict:
    if os.name != "nt":
        raise RuntimeError("Stage246 Job Object matrix must run on Windows")
    with tempfile.TemporaryDirectory(prefix="heman-stage246-job-") as temp:
        root = Path(temp)
        marker = root / "job-assigned.marker"
        log = root / "job-output.log"
        child_code = (
            "import pathlib,subprocess,sys,time\n"
            "marker=pathlib.Path(sys.argv[1])\n"
            "deadline=time.monotonic()+10\n"
            "while not marker.exists() and time.monotonic()<deadline: time.sleep(0.01)\n"
            "if not marker.exists(): raise SystemExit(9)\n"
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", child_code, str(marker)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        if proc.stdout is None:
            proc.kill()
            raise RuntimeError("synthetic parent pipe was not created")
        job = WindowsJobObject()
        try:
            job.assign(proc)
            marker.write_text("assigned\n", encoding="ascii")
            state = {
                "captured_bytes": 0, "total_bytes": 0, "truncated": False,
                "error": None, "drain_incomplete": False,
            }
            reader = threading.Thread(
                target=drain_bounded_output,
                args=(proc.stdout, log, 4096, state),
                name="stage246-windows-job-drain", daemon=True,
            )
            reader.start()
            parent_code = proc.wait(timeout=15)
            reader.join(timeout=2)
            pipe_open_after_parent = reader.is_alive()
            active_before_cleanup = job.active_process_count()
            cleanup = terminate_process_tree(proc, grace_seconds=10, job=job)
            reader.join(timeout=10)
            drain_finished = not reader.is_alive()
            result = {
                "parent_exit_code": parent_code,
                "pipe_open_after_parent_exit": pipe_open_after_parent,
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
                parent_code == 0 and pipe_open_after_parent
                and active_before_cleanup >= 1
                and cleanup["method"] == "windows_job_object_kill_on_close"
                and cleanup["success"] is True and cleanup["job_closed"] is True
                and drain_finished
            ):
                raise RuntimeError("Stage246 Windows Job Object invariant failed: "
                                   + json.dumps(result, sort_keys=True))
            return result
        finally:
            if job.is_open:
                job.close()
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "schema": "heman-stage246-windows-job-object-v1",
        "result": "windows_job_object_process_tree_pass",
        "synthetic_only": True,
        "case": run_case(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("STAGE246_WINDOWS_JOB_OBJECT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
