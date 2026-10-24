#!/usr/bin/env python3
"""Stage242 original-free consistency matrix; never a real GPU capture."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from collect_stage236_gpu_bundle import collect_bundle
from stage231_capture_session import payload

NONCE="a"*32
GPU_MARK="STAGE241_GUEST_EXIT nonce="+NONCE+" code=0\n"
PHASE="STAGE234_GPU_PHASE nonce="+NONCE+" phase=07_receipt_committed\n"
RECEIPT=("STAGE230_GPU_READBACK width=16 height=8 bytes=512 "
         "pixels=128 mismatches=0 nonce="+NONCE+"\n")
CASES=(
    ("matched_guest_return",GPU_MARK,True),
    ("no_guest_return",None,False),
    ("guest_return_25",GPU_MARK.replace("code=0","code=25"),False),
    ("guest_stale_nonce",GPU_MARK.replace(NONCE,"b"*32),False),
    ("guest_corrupted",b"\x00invalid-exit",False),
)


def case_report(guest: str | bytes | None) -> dict:
    with tempfile.TemporaryDirectory(prefix="heman-stage242-invented-") as temp:
        root=Path(temp)
        sd=root/"sd"/"switch"/"heman-stage230"
        sd.mkdir(parents=True)
        session=root/"private"
        session.mkdir()
        nro=root/"test-only.nro"
        nro_bytes=bytes(16)+b"NRO0"+b"stage242-invented-fixture"
        nro.write_bytes(nro_bytes)
        (session/"stage231_session.json").write_text(json.dumps({
            "schema":"stage231-capture-session-v1",
            "nonce":NONCE,
            "nro_sha256":hashlib.sha256(nro_bytes).hexdigest(),
            "runtime_provenance_attested":False,
        }))
        (sd/"run_nonce.txt").write_text(NONCE+"\n",encoding="ascii")
        (sd/"readback.rgba").write_bytes(payload())
        (sd/"upload.rgba").write_bytes(payload())
        (sd/"gpu_phase.txt").write_text(PHASE,encoding="ascii")
        (sd/"readback.receipt").write_text(RECEIPT,encoding="ascii")
        if guest is not None:
            (sd/"guest_exit.txt").write_bytes(
                guest.encode("ascii") if isinstance(guest,str) else guest
            )
        result=collect_bundle(nro,root/"sd",session)
    return {
        "synthetic_bundle_consistent":
            result["consistency_gate"]["synthetic_bundle_consistent"],
        "stage241_guest_reported_success":
            result["consistency_gate"]["stage241_guest_reported_success"],
        "guest_status":result["guest_exit"]["status"],
        "all_session_links_match":
            result["session_links"]["all_session_links_match"],
        "pixel_fixture_match":
            result["consistency_gate"]["both_upload_and_render_match_synthetic_fixture"],
        "runtime_gpu_execution_attested":False,
    }


def build_matrix() -> dict:
    records=[]
    for label,guest,expected in CASES:
        r=case_report(guest)
        if r["synthetic_bundle_consistent"] != expected:
            raise RuntimeError(f"Stage242 gate failed case {label}")
        if not r["pixel_fixture_match"]:
            raise RuntimeError(f"pixel fixture unexpectedly changed for case {label}")
        records.append({"scenario":label,"expected_accept":expected,**r})
    return {
        "schema":"heman-stage242-original-free-guest-exit-matrix-v1",
        "source":"invented 16x8 RGBA and fake NRO0 header",
        "cases_tested":len(records),
        "all_synthetic_cases_passed":True,
        "gpu_execution_verified":False,
        "emulator_process_executed":False,
        "original_ios_graphics_parity_verified":False,
        "cases":records,
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    data=build_matrix()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"STAGE242_GUEST_GATE_SYNTHETIC_PASS cases={len(data['cases'])}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
