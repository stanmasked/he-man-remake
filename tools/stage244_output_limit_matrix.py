#!/usr/bin/env python3
"""Stage244 source-only test: hostile child output never grows saved log past cap."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from stage240_private_emulator_launcher import (
    MAX_HOST_LOG_BYTES, drain_bounded_output,
)


def run_case() -> dict:
    emitted=MAX_HOST_LOG_BYTES+12345
    child=("import sys\n"
           "chunk=b'X'*65536\n"
           f"remaining={emitted}\n"
           "while remaining:\n"
           " n=min(remaining,len(chunk))\n"
           " sys.stdout.buffer.write(chunk[:n])\n"
           " sys.stdout.buffer.flush()\n"
           " remaining-=n\n")
    with tempfile.TemporaryDirectory(prefix="heman-stage244-synthetic-") as d:
        log=Path(d)/"bounded-host.log"
        proc=subprocess.Popen([sys.executable,"-c",child],
                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              bufsize=0)
        if proc.stdout is None:
            raise RuntimeError("pipe missing")
        state={"captured_bytes":0,"total_bytes":0,"truncated":False,
               "error":None,"drain_incomplete":False}
        reader=threading.Thread(target=drain_bounded_output,
                                args=(proc.stdout,log,MAX_HOST_LOG_BYTES,state),
                                daemon=True)
        reader.start()
        code=proc.wait(timeout=30)
        reader.join(timeout=10)
        if reader.is_alive():
            raise RuntimeError("bounded reader did not finish")
        size=log.stat().st_size
        result={
            "child_exit_code":code,
            "bytes_emitted_by_child":emitted,
            "bytes_observed_by_reader":state["total_bytes"],
            "bytes_retained":state["captured_bytes"],
            "file_size":size,
            "configured_limit":MAX_HOST_LOG_BYTES,
            "truncated":state["truncated"],
            "drain_error":state["error"],
            "drain_incomplete":state["drain_incomplete"],
            "gpu_execution_verified":False,
            "original_ios_parity_verified":False,
        }
        if not (
            code==0 and result["bytes_observed_by_reader"]==emitted
            and result["bytes_retained"]==MAX_HOST_LOG_BYTES
            and size==MAX_HOST_LOG_BYTES and result["truncated"]
            and result["drain_error"] is None
            and not result["drain_incomplete"]
        ):
            raise RuntimeError("Stage244 bounded output invariant failed")
        return result


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report={"schema":"heman-stage244-source-only-bounded-output-v1",
            "result":"bounded_output_pass","synthetic_only":True,
            "case":run_case()}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",
                           encoding="utf-8")
    print("STAGE244_BOUNDED_HOST_OUTPUT_PASS",
          report["case"]["bytes_retained"],report["case"]["bytes_observed_by_reader"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
