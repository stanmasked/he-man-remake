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
import threading

from stage231_capture_session import prepare, collect, SessionError, nro_sha256
from collect_stage236_gpu_bundle import collect_bundle, BundleError
from stage241_guest_exit_receipt import inspect_guest_exit_file
from stage251_runtime_backend_audit import analyze_file as audit_runtime_backend_log, AuditError as RuntimeBackendAuditError
from stage253_preflight_launch_gate import validate_preflight_report, PreflightGateError


class LaunchError(ValueError):
    pass


def file_sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


MAX_HOST_LOG_BYTES = 4 * 1024 * 1024
OUTPUT_CHUNK_BYTES = 64 * 1024


def drain_bounded_output(stream, log_path: Path, limit: int, state: dict) -> None:
    """Drain child output continuously while persisting at most limit bytes."""
    captured = 0
    total = 0
    try:
        with log_path.open("wb") as log:
            while True:
                chunk = stream.read(OUTPUT_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                room = max(0, limit - captured)
                if room:
                    retained = chunk[:room]
                    log.write(retained)
                    captured += len(retained)
                if len(chunk) > room:
                    state["truncated"] = True
            log.flush()
    except (OSError, ValueError) as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        state["captured_bytes"] = captured
        state["total_bytes"] = total
        try:
            stream.close()
        except (OSError, ValueError):
            pass


class WindowsJobObject:
    """Own a Windows Job Object configured to kill all assigned processes on close."""
    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows Job Objects are only available on Windows")
        import ctypes
        from ctypes import wintypes

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class BasicAccountingInformation(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._ExtendedLimitInformation = ExtendedLimitInformation
        self._BasicAccountingInformation = BasicAccountingInformation
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        self._kernel32.SetInformationJobObject.restype = wintypes.BOOL
        self._kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        self._kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL

        self.handle = self._kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimitInformation()
        # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: descendants cannot outlive owner.
        limits.BasicLimitInformation.LimitFlags = 0x00002000
        ok = self._kernel32.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
        if not ok:
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    @property
    def is_open(self) -> bool:
        return bool(self.handle)

    def assign(self, proc: subprocess.Popen) -> None:
        if not self.is_open:
            raise OSError("Windows Job Object handle is closed")
        process_handle = self._wintypes.HANDLE(int(proc._handle))
        if not self._kernel32.AssignProcessToJobObject(self.handle, process_handle):
            raise self._ctypes.WinError(self._ctypes.get_last_error())

    def active_process_count(self) -> int:
        if not self.is_open:
            raise OSError("Windows Job Object handle is closed")
        info = self._BasicAccountingInformation()
        returned = self._wintypes.DWORD()
        ok = self._kernel32.QueryInformationJobObject(
            self.handle, 1, self._ctypes.byref(info), self._ctypes.sizeof(info),
            self._ctypes.byref(returned))
        if not ok:
            raise self._ctypes.WinError(self._ctypes.get_last_error())
        return int(info.ActiveProcesses)

    def close(self) -> bool:
        if not self.is_open:
            return True
        ok = bool(self._kernel32.CloseHandle(self.handle))
        if ok:
            self.handle = None
        return ok


OUTPUT_DRAIN_GRACE_SECONDS = 2


_WINDOWS_GATED_LAUNCHER = r"""
import json
import subprocess
import sys

try:
    command_line = sys.stdin.buffer.readline()
    if not command_line:
        raise ValueError("missing gated command")
    command = json.loads(command_line.decode("utf-8"))
    if (not isinstance(command, list) or not command
            or any(not isinstance(arg, str) or not arg or "\x00" in arg
                   for arg in command)):
        raise ValueError("invalid gated command")
    if sys.stdin.buffer.readline().strip() != b"GO":
        raise ValueError("launch gate was not opened")
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL)
    raise SystemExit(child.wait())
except SystemExit:
    raise
except BaseException as exc:
    sys.stderr.write("STAGE247_GATED_LAUNCH_FAIL: %s: %s\n" %
                     (type(exc).__name__, exc))
    raise SystemExit(127)
"""


def start_windows_gated_process(command: list[str], job: WindowsJobObject,
                                log_path: Path, log_state: dict):
    """Assign a waiting trampoline to the Job before it starts the emulator."""
    if os.name != "nt":
        raise OSError("gated Windows launch is only available on Windows")
    proc = subprocess.Popen(
        [sys.executable, "-c", _WINDOWS_GATED_LAUNCHER],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, bufsize=0,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    drainer = None
    try:
        if proc.stdin is None or proc.stdout is None:
            raise OSError("gated launcher pipes were not created")
        # The trampoline blocks on stdin and cannot start the emulator yet.
        job.assign(proc)
        log_state["windows_job_object_assigned"] = True
        drainer = threading.Thread(
            target=drain_bounded_output,
            args=(proc.stdout, log_path, MAX_HOST_LOG_BYTES, log_state),
            name="heman-bounded-host-log", daemon=True)
        drainer.start()
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8")
        proc.stdin.write(payload + b"\nGO\n")
        proc.stdin.flush()
        proc.stdin.close()
        return proc, drainer
    except BaseException:
        if proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
        if job.is_open:
            job.close()
        if drainer is not None:
            drainer.join(timeout=2)
        raise


def terminate_process_tree(proc: subprocess.Popen, grace_seconds: int = 10,
                          job: WindowsJobObject | None = None) -> dict:
    """Terminate the isolated runner tree without invoking a command shell."""
    result = {
        "attempted": True,
        "method": "posix_process_group" if os.name != "nt" else (
            "windows_job_object_kill_on_close" if job is not None
            else "windows_taskkill_tree_fallback"),
        "success": False,
        "error": None,
        "parent_reaped": False,
        "job_closed": None,
        "active_processes_before_close": None,
    }
    if os.name != "nt":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            result["signal_sent"] = True
        except ProcessLookupError:
            result["signal_sent"] = False
            result["already_gone"] = True
        except OSError as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
    elif job is not None:
        try:
            result["active_processes_before_close"] = job.active_process_count()
        except OSError as exc:
            result["error"] = f"cannot query Job Object: {exc}"
        result["job_closed"] = job.close()
        if not result["job_closed"]:
            result["error"] = result["error"] or "CloseHandle(Job Object) failed"
    else:
        try:
            task = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=grace_seconds, check=False,
            )
            result["taskkill_returncode"] = task.returncode
            if task.returncode != 0:
                result["error"] = f"taskkill returned {task.returncode}"
        except (OSError, subprocess.SubprocessError) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
    if proc.poll() is None:
        try:
            proc.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait(timeout=grace_seconds)
            except (OSError, subprocess.SubprocessError) as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
    result["parent_reaped"] = proc.poll() is not None
    if os.name != "nt":
        result["success"] = result["parent_reaped"] and (
            result.get("signal_sent", False) or result.get("already_gone", False)
        ) and result["error"] is None
    else:
        if job is not None:
            result["success"] = result["parent_reaped"] and (
                result.get("job_closed") is True
            ) and result["error"] is None
        else:
            result["success"] = result["parent_reaped"] and (
                result.get("taskkill_returncode") == 0
            ) and result["error"] is None
    return result


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
           template: list[str], timeout: int, *, test_runner: bool=False,
           preflight_report: Path | None=None) -> dict:
    if type(timeout) is not int or not 10<=timeout<=3600:
        raise LaunchError("timeout must be 10–3600 seconds")
    cmd=build_command(executable,nro,template)
    validate_private_paths(sd_root,session_dir,executable,nro)
    exe_sha=file_sha(executable)
    nro_sha=nro_sha256(nro)
    preflight_gate = None
    preflight_gate_status = "bypassed_test_only_runner" if test_runner else "missing"
    if not test_runner:
        if preflight_report is None:
            raise LaunchError("real emulator launch requires a Stage252 --preflight-report")
        try:
            preflight_gate = validate_preflight_report(
                preflight_report, executable, nro, sd_root, session_dir, template
            )
            preflight_gate_status = "accepted"
        except PreflightGateError as exc:
            raise LaunchError(f"Stage252 preflight gate rejected launch: {exc}") from exc
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
    log_state={"captured_bytes":0,"total_bytes":0,"truncated":False,
               "error":None,"drain_incomplete":False,
               "tree_cleanup_attempted":False,"tree_cleanup_success":None,
               "tree_cleanup_method":None,"tree_cleanup_error":None}
    drainer=None
    proc=None
    job_object=None
    log_state.update({
        "windows_job_object_assigned":False,
        "windows_job_object_active_processes_after_parent_exit":None,
        "windows_job_object_close_success":None,
        "windows_job_object_query_error":None,
        "tree_cleanup_active_processes":None,
    })

    # Stream combined output through a bounded private log sink. Continue
    # draining after the cap so a noisy process cannot block on a full pipe.
    try:
        if os.name=="nt":
            # The gated trampoline waits for a token until after Job assignment.
            # Its emulator child and later descendants therefore join the Job.
            job_object=WindowsJobObject()
            proc,drainer=start_windows_gated_process(cmd,job_object,log_path,log_state)
        else:
            proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                  bufsize=0,start_new_session=True)
            if proc.stdout is None:
                raise LaunchError("host output pipe was not created")
            drainer=threading.Thread(
                target=drain_bounded_output,
                args=(proc.stdout,log_path,MAX_HOST_LOG_BYTES,log_state),
                name="heman-bounded-host-log",daemon=True)
            drainer.start()
        try:
            exit_code=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True
            cleanup=terminate_process_tree(proc,job=job_object)
            log_state["tree_cleanup_active_processes"]=cleanup.get("active_processes_before_close")
            log_state["windows_job_object_close_success"]=cleanup.get("job_closed")
            log_state["tree_cleanup_attempted"]=True
            log_state["tree_cleanup_success"]=cleanup["success"]
            log_state["tree_cleanup_method"]=cleanup["method"]
            log_state["tree_cleanup_error"]=cleanup["error"]
            try:
                exit_code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                exit_code=None
                log_state["error"]="runner process did not exit after tree termination"
        drainer.join(timeout=OUTPUT_DRAIN_GRACE_SECONDS)
        if drainer.is_alive():
            # A descendant may have inherited stdout/stderr after the main
            # runner exited. Kill the isolated group/tree before closing pipe.
            cleanup=terminate_process_tree(
                proc,job=job_object if job_object is not None and job_object.is_open else None)
            log_state["tree_cleanup_active_processes"]=cleanup.get("active_processes_before_close")
            log_state["windows_job_object_close_success"]=cleanup.get("job_closed")
            log_state["tree_cleanup_attempted"]=True
            log_state["tree_cleanup_success"]=cleanup["success"]
            log_state["tree_cleanup_method"]=cleanup["method"]
            log_state["tree_cleanup_error"]=cleanup["error"]
            drainer.join(timeout=OUTPUT_DRAIN_GRACE_SECONDS)
        if drainer.is_alive():
            log_state["drain_incomplete"]=True
            log_state["error"]="output drain remained open after process-tree cleanup"
            try:
                proc.stdout.close()
            except (OSError,ValueError):
                pass
            drainer.join(timeout=1)
        # If the parent exited cleanly but no pipe was left open, still query
        # the Job Object: descendants may be running without inheriting stdout.
        if (os.name=="nt" and job_object is not None and job_object.is_open
                and exit_code is not None):
            try:
                active=job_object.active_process_count()
                log_state["windows_job_object_active_processes_after_parent_exit"]=active
                if active>0:
                    cleanup=terminate_process_tree(proc,job=job_object)
                    log_state["tree_cleanup_active_processes"]=cleanup.get("active_processes_before_close")
                    log_state["windows_job_object_close_success"]=cleanup.get("job_closed")
                    log_state["tree_cleanup_attempted"]=True
                    log_state["tree_cleanup_success"]=cleanup["success"]
                    log_state["tree_cleanup_method"]=cleanup["method"]
                    log_state["tree_cleanup_error"]=cleanup["error"]
                else:
                    closed=job_object.close()
                    log_state["windows_job_object_close_success"]=closed
                    if not closed:
                        log_state["error"]="could not close empty Windows Job Object"
            except OSError as exc:
                log_state["windows_job_object_query_error"]=f"{type(exc).__name__}: {exc}"
                cleanup=terminate_process_tree(proc,job=job_object)
                log_state["tree_cleanup_active_processes"]=cleanup.get("active_processes_before_close")
                log_state["windows_job_object_close_success"]=cleanup.get("job_closed")
                log_state["tree_cleanup_attempted"]=True
                log_state["tree_cleanup_success"]=False
                log_state["tree_cleanup_method"]=cleanup["method"]
                log_state["tree_cleanup_error"]=str(exc)
                log_state["error"]="could not verify Windows Job Object process count"
    except (OSError,subprocess.SubprocessError) as exc:
        error=f"{type(exc).__name__}: {exc}"
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=10)
            except (OSError,subprocess.SubprocessError):
                pass
        if job_object is not None and job_object.is_open:
            log_state["windows_job_object_close_success"]=job_object.close()
        if drainer is not None:
            drainer.join(timeout=2)
            if drainer.is_alive():
                log_state["drain_incomplete"]=True
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
        if log_state["truncated"]:
            collection_error=(
                f"host log exceeded {MAX_HOST_LOG_BYTES} bytes; "
                "output was truncated and Stage231 collection was skipped")
        elif log_state["error"] or log_state["drain_incomplete"]:
            collection_error="host output drain failed or did not complete"
        elif log_state["tree_cleanup_attempted"]:
            collection_error=(
                "process-tree cleanup was required after runner exit; "
                "Stage231 collection skipped")
        else:
            try:
                collect(nro,sd_root,session_dir,
                        runner_log_path=log_path,exit_status_path=exit_path,
                        runtime="gpu_capable_emulator",
                        command=json.dumps(cmd))
                collected=True
            except (SessionError,OSError,UnicodeError,ValueError) as exc:
                collection_error=f"{type(exc).__name__}: {exc}"

    bundle_consistent=False
    bundle_error=None
    try:
        bundle=collect_bundle(nro,sd_root,session_dir)
        bundle_consistent=bundle["consistency_gate"]["synthetic_bundle_consistent"]
        (session_dir/"stage240_bundle.json").write_text(
            json.dumps(bundle,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    except (BundleError,SessionError,OSError,ValueError) as exc:
        bundle_error=f"{type(exc).__name__}: {exc}"

    # Stage241: the host process may close with 0 without ever executing the
    # guest NRO. Require a separate nonce-matching guest-side CPU receipt.
    # The file itself is forgeable and NEVER attests the GPU backend.
    guest_exit=inspect_guest_exit_file(
        sd_root/"switch"/"heman-stage230"/"guest_exit.txt",
        prepared["nonce"])
    guest_success=guest_exit["guest_reported_success"]
    backend_audit = None
    backend_audit_status = "skipped_log_unavailable"
    backend_audit_error = None
    if log_path.exists():
        if log_state["truncated"] or log_state["drain_incomplete"] or log_state["error"]:
            backend_audit_status = "skipped_log_incomplete"
        else:
            try:
                backend_audit = audit_runtime_backend_log(log_path)
                backend_audit_status = "complete"
            except (RuntimeBackendAuditError, OSError) as exc:
                backend_audit_status = "failed"
                backend_audit_error = f"{type(exc).__name__}: {exc}"
    manifest={
        "schema":"stage240-host-emulator-attempt-v1",
        "prepared_session_nonce":prepared["nonce"],
        "nro_sha256":nro_sha,
        "emulator_executable_sha256":exe_sha,
        "stage252_preflight_gate_status":preflight_gate_status,
        "stage252_preflight_gate":preflight_gate,
        "emulator_command":cmd,
        "host_process_role":"windows_gated_launcher_wrapper" if os.name=="nt" else "emulator_process",
        "windows_gated_launch_used":os.name=="nt",
        "started_utc":started,
        "ended_utc":ended,
        "host_process_exit_code":exit_code,
        "host_timed_out":timed_out,
        "host_launch_error":error,
        "runner_log_sha256":file_sha(log_path) if log_path.exists() and not log_state["drain_incomplete"] else None,
        "runner_log_bytes":log_path.stat().st_size if log_path.exists() and not log_state["drain_incomplete"] else None,
        "runner_log_bytes_captured":log_state["captured_bytes"],
        "runner_log_bytes_observed":log_state["total_bytes"],
        "runner_log_limit_bytes":MAX_HOST_LOG_BYTES,
        "runner_log_truncated":log_state["truncated"],
        "runner_log_drain_error":log_state["error"],
        "runner_log_drain_incomplete":log_state["drain_incomplete"],
        "runtime_backend_log_audit_status":backend_audit_status,
        "runtime_backend_log_audit":backend_audit,
        "runtime_backend_log_audit_error":backend_audit_error,
        "process_tree_cleanup_attempted":log_state["tree_cleanup_attempted"],
        "process_tree_cleanup_success":log_state["tree_cleanup_success"],
        "process_tree_cleanup_method":log_state["tree_cleanup_method"],
        "process_tree_cleanup_error":log_state["tree_cleanup_error"],
        "process_tree_cleanup_active_processes":log_state["tree_cleanup_active_processes"],
        "windows_job_object_assigned":log_state["windows_job_object_assigned"],
        "windows_job_object_active_processes_after_parent_exit":log_state["windows_job_object_active_processes_after_parent_exit"],
        "windows_job_object_close_success":log_state["windows_job_object_close_success"],
        "windows_job_object_query_error":log_state["windows_job_object_query_error"],
        "stage231_collected":collected,
        "stage231_collection_error":collection_error,
        "stage236_bundle_consistent":bundle_consistent,
        "stage236_bundle_error":bundle_error,
        "stage241_guest_exit_receipt":guest_exit,
        "stage241_guest_exit_receipt_accepted":guest_success,
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
    ap.add_argument("--preflight-report",type=Path,
                    help="fresh Stage252 report matching this exact emulator/NRO/SD root/session/argument template")
    ap.add_argument("launch_args",nargs=argparse.REMAINDER,
                    help="after --: exact emulator arguments incl. one literal {nro}")
    a=ap.parse_args()
    args=a.launch_args[1:] if a.launch_args[:1]==["--"] else a.launch_args
    try:
        result=launch(a.emulator,a.nro,a.sd_root,a.session_dir,args,
                      a.timeout,test_runner=a.test_only_runner,
                      preflight_report=a.preflight_report)
    except (LaunchError,SessionError,OSError,ValueError) as exc:
        print(f"STAGE240_FAIL: {exc}",file=sys.stderr)
        return 1
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result["stage231_collected"] and result["stage236_bundle_consistent"] and result["stage241_guest_exit_receipt_accepted"] else 2


if __name__=="__main__":
    raise SystemExit(main())
