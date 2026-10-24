#!/usr/bin/env python3
"""Stage245 synthetic test: close inherited output pipes after parent exit."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from stage240_private_emulator_launcher import (
    OUTPUT_DRAIN_GRACE_SECONDS, drain_bounded_output, terminate_process_tree,
)


def run_case() -> dict:
    # The child process exits immediately after spawning a 60-second
    # descendant which inherits stdout. This is invented host behavior only.
    child = (
        "import subprocess,sys\n"
        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
    )
    with tempfile.TemporaryDirectory(prefix="heman-stage245-tree-") as temp:
        log = Path(temp) / "host-launch.log"
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(
            [sys.executable, "-c", child],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
            start_new_session=(os.name != "nt"), creationflags=flags,
        )
        if proc.stdout is None:
            raise RuntimeError("synthetic child pipe not created")
        state = {
            "captured_bytes": 0, "total_bytes": 0, "truncated": False,
            "error": None, "drain_incomplete": False,
        }
        reader = threading.Thread(
            target=drain_bounded_output,
            args=(proc.stdout, log, 4096, state),
            name="stage245-synthetic-drain", daemon=True,
        )
        reader.start()
        parent_code = proc.wait(timeout=10)
        reader.join(timeout=OUTPUT_DRAIN_GRACE_SECONDS)
        blocked_before_cleanup = reader.is_alive()
        cleanup = None
        if blocked_before_cleanup:
            cleanup = terminate_process_tree(proc, grace_seconds=5)
            reader.join(timeout=OUTPUT_DRAIN_GRACE_SECONDS)
        drain_finished = not reader.is_alive()
        if not drain_finished:
            try:
                proc.stdout.close()
            except (OSError, ValueError):
                pass
            reader.join(timeout=1)
        result = {
            "parent_exit_code": parent_code,
            "pipe_stayed_open_after_parent_exit": blocked_before_cleanup,
            "process_tree_cleanup_attempted": cleanup is not None,
            "process_tree_cleanup": cleanup,
            "drain_finished_after_cleanup": drain_finished,
            "log_size_bytes": log.stat().st_size if log.exists() else None,
            "gpu_execution_verified": False,
            "original_ios_parity_verified": False,
        }
        if not (
            parent_code == 0 and blocked_before_cleanup
            and cleanup is not None and cleanup["success"]
            and drain_finished
        ):
            raise RuntimeError("Stage245 failed to close inherited output pipe")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "schema": "heman-stage245-process-tree-cleanup-v1",
        "result": "synthetic_process_tree_cleanup_pass",
        "synthetic_only": True,
        "case": run_case(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("STAGE245_SYNTHETIC_PROCESS_TREE_CLEANUP_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
