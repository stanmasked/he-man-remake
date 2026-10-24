#!/usr/bin/env python3
"""Stage240 private emulator launcher for Stage234's deko3d synthetic NRO.

Runs only a caller-supplied *installed* executable without a shell. It records
real host process exit/log hashes but never attests GPU/guest execution.
Nothing is uploaded by this tool. Store all outputs owner-private.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from stage231_capture_session import prepare, collect, SessionError, nro_sha256


class LaunchError(ValueError):
    pass


def file_sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_command(executable: Path, nro: Path,
                  template: list[str]) -> list[str]:
    """Require an actual executable and a single exact {nro} argument slot."""
    if not executable.is_absolute() or not executable.is_file():
        raise LaunchError("emulator executable must be an existing absolute file")
    if not os.access(executable, os.X_OK):
        raise LaunchError("emulator file is not executable")
    if not nro.is_file() or not nro.is_absolute():
        raise LaunchError("NRO must be an existing absolute file")
    nro_sha256(nro)
    if template.count("{nro}")!=1:
        raise LaunchError("launch arguments must contain {nro} exactly once")
    if not template or len(template)>40 or any(
        not isinstance(arg,str) or not arg or "\x00" in arg for arg in template
    ):
        raise LaunchError("invalid emulator argument list")
    if any("{nro}" in arg and arg!="{nro}" for arg in template):
        raise LaunchError("NRO placeholder must be an entire argument")
    if executable.resolve()==nro.resolve():
        raise LaunchError("emulator path must differ from NRO")
    return [str(executable)]+[
        str(nro) if arg=="{nro}" else arg for arg in template
    ]


def validate_private_paths(sd_root: Path, session_dir: Path,
                           executable: Path, nro: Path) -> None:
    if not sd_root.is_absolute() or not session_dir.is_absolute():
        raise LaunchError("SD root and session directory must be absolute")
    if not sd_root.is_dir():
        raise LaunchError("emulator SD root must already exist; never guess it")
    if session_dir.exists() and (not session_dir.is_dir() or any(session_dir.iterdir())):
        raise LaunchError("session output must be a fresh empty private directory")
    if session_dir.resolve() == sd_root.resolve() or sd_root.resolve() in session_dir.resolve().parents:
        raise LaunchError("session output must not be inside the emulator SD directory")
    if session_dir.resolve() in sd_root.resolve().parents:
        raise LaunchError("SD root must not be within the session output directory")
    if session_dir.resolve() in executable.resolve().parents:
        raise LaunchError("session directory must not contain the emulator executable")
    if session_dir.resolve() in nro.resolve().parents:
        raise LaunchError("session directory must not contain the NRO")


def launch(executable: Path, nro: Path, sd_root: Path, session_dir: Path,
           template: list[str], timeout: int, *, test_runner: bool=False) -> dict:
    if type(timeout) is not int or not 10<=timeout<=3600:
        raise LaunchError("timeout must be 10–3600 seconds")
    cmd=build_command(executable,nro,template)
    validate_private_paths(sd_root,session_dir,executable,nro)
    exe_sha=file_sha(executable)
    nro_sha=nro_sha256(nro)
    prepared=prepare(nro,sd_root,session_dir)
    if prepared["nro_sha256"]!=nro_sha:
        raise LaunchError("NRO changed during session preparation")
    log_path=session_dir/"host-launch.log"
    exit_path=session_dir/"runner-exit-status.txt"
    metadata_path=session_dir/"stage240_launch.json"
    started=dt.datetime.now(dt.timezone.utc).isoformat()
    timed_out=False
    exit_code=None
    error=None

    # Store logs only in owner-private session folder. Never use shell=True.
    try:
        with log_path.open("wb") as log:
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=="nt" else 0
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,
                                  start_new_session=(os.name!="nt"),
                                  creationflags=creationflags)
            try:
                exit_code=proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out=True
                if os.name!="nt":
                    try:
                        os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    proc.kill()
                exit_code=proc.wait(timeout=10)
    except (OSError,subprocess.SubprocessError) as exc:
        error=f"{type(exc).__name__}: {exc}"
    ended=dt.datetime.now(dt.timezone.utc).isoformat()
    # Distinguish timeout from an actual process exit code.
    if exit_code is None:
        exit_path.write_text("127\n",encoding="ascii")
    elif timed_out:
        exit_path.write_text("124\n",encoding="ascii")
    else:
        exit_path.write_text(f"{exit_code}\n",encoding="ascii")

    collected=False
    collection_error=None
    # An emulator's zero process exit is not necessarily the NRO's guest
    # exit. Stage231 collects bytes only as supplied evidence, never attests.
    if exit_code==0 and not timed_out and error is None:
        try:
            collect(nro,sd_root,session_dir,
                    runner_log_path=log_path,exit_status_path=exit_path,
                    runtime="gpu_capable_emulator",
                    command=json.dumps(cmd))
            collected=True
        except (SessionError,OSError,UnicodeError,ValueError) as exc:
            collection_error=f"{type(exc).__name__}: {exc}"

    manifest={
        "schema":"stage240-host-emulator-attempt-v1",
        "prepared_session_nonce":prepared["nonce"],
        "nro_sha256":nro_sha,
        "emulator_executable_sha256":exe_sha,
        "emulator_command":cmd,
        "started_utc":started,
        "ended_utc":ended,
        "host_process_exit_code":exit_code,
        "host_timed_out":timed_out,
        "host_launch_error":error,
        "runner_log_sha256":file_sha(log_path) if log_path.exists() else None,
        "runner_log_bytes":log_path.stat().st_size if log_path.exists() else None,
        "stage231_collected":collected,
        "stage231_collection_error":collection_error,
        "emulator_gpu_capability_independently_verified":False,
        "guest_process_exit_independently_verified":False,
        "runtime_gpu_execution_attested":False,
        "test_only_runner_declared":test_runner,
        "note":"Host process completion and claimed GPU output are not independent guest/GPU provenance.",
    }
    metadata_path.write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",
                             encoding="utf-8")
    return manifest


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--emulator",type=Path,required=True,
                    help="absolute path to an installed emulator executable")
    ap.add_argument("--nro",type=Path,required=True)
    ap.add_argument("--sd-root",type=Path,required=True,
                    help="existing *actual* sdmc root mapped by emulator")
    ap.add_argument("--session-dir",type=Path,required=True,
                    help="new owner-private empty directory")
    ap.add_argument("--timeout",type=int,default=300)
    ap.add_argument("--test-only-runner",action="store_true",
                    help="explicit marker for local/CI fake runner regression")
    ap.add_argument("launch_args",nargs=argparse.REMAINDER,
                    help="after --: exact emulator arguments incl. one literal {nro}")
    a=ap.parse_args()
    args=a.launch_args[1:] if a.launch_args[:1]==["--"] else a.launch_args
    try:
        result=launch(a.emulator,a.nro,a.sd_root,a.session_dir,args,
                      a.timeout,test_runner=a.test_only_runner)
    except (LaunchError,SessionError,OSError,ValueError) as exc:
        print(f"STAGE240_FAIL: {exc}",file=sys.stderr)
        return 1
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result["stage231_collected"] else 2


if __name__=="__main__":
    raise SystemExit(main())
