#!/usr/bin/env python3
"""Stage233: compare independent submitted GPU upload and shader readback files.

Two matching 512-byte files plus a nonce receipt are more diagnostic than
one frame; they do NOT independently prove graphics hardware execution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from stage231_capture_session import payload, nro_sha256, SessionError


class RoundtripError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(upload: bytes, render: bytes, session: dict,
           collected: dict, receipt: str, nro_digest: str) -> dict:
    if type(upload) is not bytes or len(upload) != 512:
        raise RoundtripError("GPU upload roundtrip must contain exactly 512 bytes")
    if type(render) is not bytes or len(render) != 512:
        raise RoundtripError("render readback must contain exactly 512 bytes")
    expected=payload()
    if upload!=expected:
        byte=next(i for i,(x,y) in enumerate(zip(upload,expected)) if x!=y)
        raise RoundtripError(f"upload mismatch pixel={byte//4} channel={byte%4}")
    if render!=expected:
        byte=next(i for i,(x,y) in enumerate(zip(render,expected)) if x!=y)
        raise RoundtripError(f"render mismatch pixel={byte//4} channel={byte%4}")
    if session.get("schema")!="stage231-capture-session-v1":
        raise RoundtripError("invalid prepared session")
    nonce=session.get("nonce")
    if not isinstance(nonce,str) or len(nonce)!=32:
        raise RoundtripError("missing session nonce")
    if receipt != (
        "STAGE230_GPU_READBACK width=16 height=8 bytes=512 "
        f"pixels=128 mismatches=0 nonce={nonce}\n"
    ):
        raise RoundtripError("missing or stale nonce-bound render completion")
    if session.get("nro_sha256")!=nro_digest:
        raise RoundtripError("wrong NRO for this session")
    if collected.get("schema")!="stage231-collected-synthetic-gpu-evidence-v1":
        raise RoundtripError("Stage231 complete run collection missing")
    if collected.get("result")!="submitted_capture_matches_challenge_and_pixels":
        raise RoundtripError("Stage231 collected report failed")
    if collected.get("nonce")!=nonce or collected.get("nro_sha256")!=nro_digest:
        raise RoundtripError("collected session or NRO changed")
    if collected.get("rgba_sha256")!=sha(render):
        raise RoundtripError("render bytes differ from collected Stage231 receipt")
    if collected.get("runtime_provenance_attested") is not False:
        raise RoundtripError("Stage231 report must not falsely claim GPU provenance")
    return {
        "schema": "stage233-verified-dual-capture-v1",
        "result": "submitted_upload_and_render_bytes_match",
        "nonce": nonce,
        "nro_sha256": nro_digest,
        "upload_rgba_sha256":sha(upload),
        "render_rgba_sha256":sha(render),
        "upload_pixels":128,
        "render_pixels":128,
        "bytes_per_capture":512,
        "runtime_gpu_execution_attested":False,
        "warning":"Matching binary outputs and nonce alone do not attest GPU execution.",
    }


def collect(nro:Path,sd_root:Path,session_dir:Path)->dict:
    if (session_dir/"stage233_dual_capture.json").exists():
        raise RoundtripError("already collected Stage233; use fresh Stage231 session")
    original=session_dir/"readback.rgba"
    if not original.is_file() or original.stat().st_size!=512:
        raise RoundtripError("Stage231 render readback missing or wrong size")
    upload_path=sd_root/"switch"/"heman-stage230"/"upload.rgba"
    if not upload_path.is_file() or upload_path.stat().st_size!=512:
        raise RoundtripError("GPU upload readback missing or wrong size")
    session=json.loads((session_dir/"stage231_session.json").read_text(encoding="utf-8"))
    collected=json.loads((session_dir/"stage231_collected.json").read_text(encoding="utf-8"))
    receipt=(session_dir/"readback.receipt").read_text(encoding="ascii")
    upload=upload_path.read_bytes()
    render=original.read_bytes()
    report=verify(upload,render,session,collected,receipt,nro_sha256(nro))
    # Store raw GPU upload only in the same owner-private session directory.
    shutil.copyfile(upload_path,session_dir/"upload.rgba")
    (session_dir/"stage233_dual_capture.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return report


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nro",type=Path,required=True)
    parser.add_argument("--sd-root",type=Path,required=True)
    parser.add_argument("--session-dir",type=Path,required=True)
    args=parser.parse_args()
    try:
        report=collect(args.nro,args.sd_root,args.session_dir)
    except (RoundtripError,SessionError,OSError,UnicodeError,json.JSONDecodeError) as e:
        print(f"STAGE233_FAIL: {e}",file=sys.stderr)
        return 1
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
