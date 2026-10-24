#!/usr/bin/env python3
"""Stage234 fail-closed GPU checkpoint parser and compile-time source audit.

A phase is a CPU-side control-flow claim. It does NOT attest execution by GPU.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

PHASES=(
    "01_nonce_validated",
    "02_shaders_loaded",
    "03_texture_upload_queue_idle",
    "04_upload_pixels_match",
    "05_render_queue_idle",
    "06_receipt_committed",
)
PHASE=re.compile(
    rb"STAGE234_GPU_PHASE nonce=([0-9a-f]{32}) phase=([0-9a-z_]+)\n"
)
RECEIPT=re.compile(
    r"STAGE230_GPU_READBACK width=16 height=8 bytes=512 "
    r"pixels=128 mismatches=0 nonce=([0-9a-f]{32})\n"
)
NONCE=re.compile(r"[0-9a-f]{32}")


class PhaseEvidenceError(ValueError):
    pass


def audit_source(source: str) -> dict:
    """Check source-level ordering. This has no GPU runtime evidentiary value."""
    if type(source) is not str or len(source)>256_000:
        raise PhaseEvidenceError("invalid source")
    guards=[
        'DkInvalidateFlags_Image|DkInvalidateFlags_Descriptors|',
        'DkInvalidateFlags_Shader);',
        'cmd.barrier(DkBarrier_Full,',
        'cmd.copyImageToBuffer(outputView',
        'queue.waitIdle();',
        '"sdmc:/switch/heman-stage230/gpu_phase.txt"',
        '"sdmc:/switch/heman-stage230/gpu_phase.tmp"',
    ]
    for g in guards:
        if g not in source:
            raise PhaseEvidenceError(f"missing GPU cache/phase source guard: {g}")
    draw_start=source.find("static int runStage228Draw(")
    draw_end=source.find("// Stage233 stores",draw_start)
    main_start=source.find("int main(int argc, char** argv)")
    if min(draw_start,draw_end,main_start)<0:
        raise PhaseEvidenceError("draw/main C++ functions not found")
    draw=source[draw_start:draw_end]
    main_source=source[main_start:]
    for subset,region in ((PHASES[:4],main_source),(PHASES[4:],draw)):
        positions=[]
        for phase in subset:
            marker=f'saveStage234Checkpoint("{phase}")'
            if source.count(marker)!=1 or region.count(marker)!=1:
                raise PhaseEvidenceError(f"expected exactly one ordered call: {phase}")
            positions.append(region.index(marker))
        if positions!=sorted(positions):
            raise PhaseEvidenceError("checkpoint calls are out of order")
    before=draw.index("cmd.barrier(DkBarrier_Full,")
    after=draw.index("cmd.copyImageToBuffer(outputView")
    if not before<after:
        raise PhaseEvidenceError("image cache barrier must precede render readback")
    if draw.count('DkInvalidateFlags_Image|DkInvalidateFlags_Descriptors|')!=1:
        raise PhaseEvidenceError("expected single draw-time texture invalidation")
    return {
        "schema":"stage234-source-preflight-v1",
        "source_guard":"passed_synthetic_source_audit",
        "checkpoint_count":len(PHASES),
        "gpu_executed":False,
    }


def check(phase_bytes:bytes,session:dict,receipt:str|None=None,
          *,require_complete:bool=False)->dict:
    if type(phase_bytes) is not bytes or len(phase_bytes)>256:
        raise PhaseEvidenceError("GPU checkpoint missing or too large")
    match=PHASE.fullmatch(phase_bytes)
    if not match:
        raise PhaseEvidenceError("malformed checkpoint or nonce")
    nonce=match[1].decode("ascii")
    phase=match[2].decode("ascii")
    if phase not in PHASES:
        raise PhaseEvidenceError("unknown checkpoint phase")
    if not isinstance(session,dict) or session.get("schema")!="stage231-capture-session-v1":
        raise PhaseEvidenceError("prepared Stage231 session unavailable")
    if session.get("nonce")!=nonce or not NONCE.fullmatch(nonce):
        raise PhaseEvidenceError("prepared session nonce does not match checkpoint")
    if require_complete and phase!=PHASES[-1]:
        raise PhaseEvidenceError("capture never reached committed receipt")
    if phase==PHASES[-1] or require_complete:
        if type(receipt) is not str:
            raise PhaseEvidenceError("completed checkpoint without guest receipt")
        completed=RECEIPT.fullmatch(receipt)
        if not completed or completed[1]!=nonce:
            raise PhaseEvidenceError("completed phase has missing/stale/mismatch receipt")
    return {
        "schema":"stage234-submitted-gpu-phase-v1",
        "phase":phase,
        "phase_index":PHASES.index(phase)+1,
        "completed":phase==PHASES[-1],
        "nonce":nonce,
        "phase_sha256":hashlib.sha256(phase_bytes).hexdigest(),
        "gpu_execution_independently_attested":False,
        "caution":"A nonce-bound CPU checkpoint does not prove GPU commands ran.",
    }


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase",type=Path,required=True)
    p.add_argument("--session",type=Path,required=True)
    p.add_argument("--receipt",type=Path)
    p.add_argument("--require-complete",action="store_true")
    p.add_argument("--source",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    try:
        if a.phase.stat().st_size>256:
            raise PhaseEvidenceError("checkpoint too large")
        session=json.loads(a.session.read_text(encoding="utf-8"))
        receipt=None if a.receipt is None else a.receipt.read_text(encoding="ascii")
        report=check(a.phase.read_bytes(),session,receipt,require_complete=a.require_complete)
        if a.source:
            report["source_preflight"]=audit_source(a.source.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,json.JSONDecodeError,PhaseEvidenceError) as e:
        print(f"STAGE234_FAIL: {e}",file=sys.stderr)
        return 1
    data=json.dumps(report,indent=2,sort_keys=True)+"\n"
    if a.output:
        a.output.write_text(data,encoding="utf-8")
    print(data,end="")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
