#!/usr/bin/env python3
"""Stage231 manual/runner handoff: non-reusable synthetic GPU capture challenge.

PREPARE runs before launching a Switch GPU-capable runtime. COLLECT processes
its separately recorded exit and raw SD results. Neither stage can attest
hardware/GPU execution on its own. Never put private raw captures in public CI.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys

BYTES = 512
NONCE = re.compile(r"[0-9a-f]{32}")
RECEIPT = re.compile(
    r"STAGE230_GPU_READBACK width=(\d+) height=(\d+) bytes=(\d+) "
    r"pixels=(\d+) mismatches=(\d+) nonce=([0-9a-f]{32})\n?"
)


class SessionError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload() -> bytes:
    out = bytearray()
    for y in range(8):
        for x in range(16):
            out.extend((x*20, y*30, x+y, 255) if x < 9 and y < 5
                       else (0, 0, 0, 255))
    return bytes(out)


def nro_sha256(nro_file: Path) -> str:
    if not nro_file.is_file() or not 20 <= nro_file.stat().st_size <= 16*1024*1024:
        raise SessionError("invalid NRO size")
    data = nro_file.read_bytes()
    if data[16:20] != b"NRO0":
        raise SessionError("NRO0 header missing")
    return digest(data)


def sd_dir(root: Path) -> Path:
    return root / "switch" / "heman-stage230"


def prepare(nro: Path, sd_root: Path, output_dir: Path, *, challenge: str | None = None) -> dict:
    binary_digest = nro_sha256(nro)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SessionError("session output directory is not empty")
    if challenge is None:
        challenge = secrets.token_hex(16)
    if not NONCE.fullmatch(challenge):
        raise SessionError("challenge must be 128-bit lowercase hex")
    output_dir.mkdir(parents=True, exist_ok=True)
    sd = sd_dir(sd_root)
    sd.mkdir(parents=True, exist_ok=True)
    # Stale artifacts must be removed before guest startup; never touch
    # original commercial files or paths outside the synthetic test folder.
    for name in (
        "readback.rgba", "readback.receipt",
        "readback.rgba.tmp", "readback.receipt.tmp",
        "upload.rgba", "upload.rgba.tmp",
        "gpu_phase.txt", "gpu_phase.tmp",
        "guest_exit.txt", "guest_exit.tmp",
        "run_nonce.txt.tmp",
    ):
        (sd / name).unlink(missing_ok=True)
    nonce_tmp = sd / "run_nonce.txt.tmp"
    nonce_final = sd / "run_nonce.txt"
    try:
        nonce_tmp.write_text(challenge + "\n", encoding="ascii")
        # os.replace replaces a pre-existing symlink itself rather than
        # following it, and the reader sees either the old or full new file.
        os.replace(nonce_tmp, nonce_final)
    except OSError as exc:
        nonce_tmp.unlink(missing_ok=True)
        raise SessionError("could not atomically write SD session nonce") from exc
    request = {
        "schema": "stage231-capture-session-v1",
        "state": "prepared_not_executed",
        "nonce": challenge,
        "nro_sha256": binary_digest,
        "nro_file_name": nro.name,
        "prepared_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runtime_provenance_attested": False,
        "note": "Preparation does not execute a GPU, Switch or emulator.",
    }
    (output_dir / "stage231_session.json").write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return request


def validate(session: dict, nonce_text: str, rgba: bytes, receipt: str,
             nro_digest: str, exit_status: int, runner_log: bytes,
             runtime: str, command: str) -> dict:
    if session.get("schema") != "stage231-capture-session-v1":
        raise SessionError("unexpected session schema")
    nonce = session.get("nonce")
    if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
        raise SessionError("invalid prepared nonce")
    if nonce_text != nonce + "\n":
        raise SessionError("SD request does not match host-generated challenge")
    if session.get("nro_sha256") != nro_digest:
        raise SessionError("different NRO than the prepared launch")
    if type(exit_status) is not int or exit_status != 0:
        raise SessionError("guest/runner exit is not zero")
    if runtime not in ("switch_hardware", "gpu_capable_emulator"):
        raise SessionError("CPU-only/unknown runtime cannot establish GPU execution")
    if not isinstance(command, str) or not command.strip():
        raise SessionError("missing actual launcher command")
    if not runner_log or len(runner_log) > 4*1024*1024:
        raise SessionError("runner log absent/oversized")
    match = RECEIPT.fullmatch(receipt)
    if not match:
        raise SessionError("missing/malformed Stage231 receipt")
    width, height, size, pixels, mismatches, observed_nonce = match.groups()
    if tuple(map(int, (width, height, size, pixels, mismatches))) != (16, 8, 512, 128, 0):
        raise SessionError("wrong readback parameters or guest mismatch report")
    if observed_nonce != nonce:
        raise SessionError("receipt nonce does not match prepared run")
    if len(rgba) != BYTES:
        raise SessionError("readback byte count mismatch")
    ref = payload()
    if rgba != ref:
        offset = next(i for i, (a,b) in enumerate(zip(rgba, ref)) if a != b)
        raise SessionError(f"RGBA mismatch pixel={offset//4} channel={offset%4}")
    return {
        "schema": "stage231-collected-synthetic-gpu-evidence-v1",
        "result": "submitted_capture_matches_challenge_and_pixels",
        "nonce": nonce,
        "nro_sha256": nro_digest,
        "rgba_sha256": digest(rgba),
        "receipt_sha256": digest(receipt.encode("ascii")),
        "runner_log_sha256": digest(runner_log),
        "byte_count": BYTES,
        "pixel_count": 128,
        "runtime_submitted": runtime,
        "runtime_provenance_attested": False,
        "warning": "Nonce/bytes/exit/log alone do not prove true GPU execution; require independent runner/device GPU diagnostics.",
    }


def collect(nro: Path, sd_root: Path, output_dir: Path, *,
            runner_log_path: Path, exit_status_path: Path,
            runtime: str, command: str) -> dict:
    manifest = output_dir / "stage231_session.json"
    if not manifest.is_file():
        raise SessionError("missing previously prepared session")
    if (output_dir / "stage231_collected.json").exists():
        raise SessionError("session was already collected; create a fresh session")
    session = json.loads(manifest.read_text(encoding="utf-8"))
    sd = sd_dir(sd_root)
    status_text = exit_status_path.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9]{1,3}", status_text):
        raise SessionError("invalid independent exit status")
    rgba_file, receipt_file = sd/"readback.rgba", sd/"readback.receipt"
    if not rgba_file.is_file() or rgba_file.stat().st_size != BYTES:
        raise SessionError("missing or incorrectly sized GPU readback file")
    if not receipt_file.is_file() or receipt_file.stat().st_size > 256:
        raise SessionError("missing/oversized completion receipt")
    if runner_log_path.stat().st_size > 4*1024*1024:
        raise SessionError("runner log oversized")
    result = validate(
        session,
        (sd/"run_nonce.txt").read_text(encoding="ascii"),
        rgba_file.read_bytes(),
        receipt_file.read_text(encoding="ascii"),
        nro_sha256(nro),
        int(status_text),
        runner_log_path.read_bytes(),
        runtime, command)
    # Store raw evidence only in the PRIVATE session location; public GitHub
    # workflows must neither invoke COLLECT nor upload these files.
    shutil.copyfile(rgba_file, output_dir / "readback.rgba")
    shutil.copyfile(receipt_file, output_dir / "readback.receipt")
    shutil.copyfile(runner_log_path, output_dir / "runtime.log")
    shutil.copyfile(exit_status_path, output_dir / "exit-status.txt")
    (output_dir / "stage231_collected.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="operation", required=True)
    for name in ("prepare", "collect"):
        s = sub.add_parser(name)
        s.add_argument("--nro", type=Path, required=True)
        s.add_argument("--sd-root", type=Path, required=True)
        s.add_argument("--session-dir", type=Path, required=True)
        if name == "collect":
            s.add_argument("--runner-log", type=Path, required=True)
            s.add_argument("--exit-status", type=Path, required=True)
            s.add_argument("--runtime", choices=["switch_hardware","gpu_capable_emulator"], required=True)
            s.add_argument("--command", required=True, help="Actual command recorded by the runner, not a guessed emulator invocation")
    a = p.parse_args()
    try:
        if a.operation == "prepare":
            result = prepare(a.nro, a.sd_root, a.session_dir)
        else:
            result = collect(a.nro, a.sd_root, a.session_dir,
                runner_log_path=a.runner_log, exit_status_path=a.exit_status,
                runtime=a.runtime, command=a.command)
    except (SessionError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print("STAGE231_FAIL:", exc, file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
