#!/usr/bin/env python3
"""Stage243 original-free fixed-size and oversize input rejection matrix."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tempfile

from stage243_bounded_evidence import (
    EvidenceReadError, read_limited,
    MAX_RGBA_BYTES, MAX_LOG_BYTES, MAX_MANIFEST_BYTES, MAX_RECEIPT_BYTES,
)

CASES=(
    ("exact_rgba",MAX_RGBA_BYTES,MAX_RGBA_BYTES,True),
    ("oversized_rgba",MAX_RGBA_BYTES+1,MAX_RGBA_BYTES,False),
    ("exact_receipt",MAX_RECEIPT_BYTES,MAX_RECEIPT_BYTES,True),
    ("oversized_receipt",MAX_RECEIPT_BYTES+1,MAX_RECEIPT_BYTES,False),
    ("oversized_manifest",MAX_MANIFEST_BYTES+1,MAX_MANIFEST_BYTES,False),
    ("oversized_log",MAX_LOG_BYTES+1,MAX_LOG_BYTES,False),
)


def matrix()->dict:
    results=[]
    with tempfile.TemporaryDirectory(prefix="stage243-invented-evidence-") as d:
        path=Path(d)/"temporary-only"
        for name,length,limit,expected in CASES:
            with path.open("wb") as output:
                output.truncate(length) # sparse, invented file
            try:
                read_limited(path,limit,name)
                accepted=True
            except EvidenceReadError:
                accepted=False
            if accepted!=expected:
                raise RuntimeError(f"Stage243 bounds regression: {name}")
            results.append({
                "name":name,"file_size":length,"read_limit":limit,
                "expected_accept":expected,"actual_accept":accepted,
            })
    return {
        "schema":"stage243-source-only-bounded-file-matrix-v1",
        "result":"all_synthetic_size_limits_enforced",
        "cases_tested":len(results),
        "gpu_execution_verified":False,
        "emulator_run_verified":False,
        "original_ios_parity_verified":False,
        "case_results":results,
    }


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    report=matrix()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",
                        encoding="utf-8")
    print("STAGE243_SOURCE_ONLY_BOUND_CHECK_PASS",report["cases_tested"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
