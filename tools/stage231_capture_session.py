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
import stat
import secrets
import shutil
import sys
from stage243_bounded_evidence import (
    EvidenceReadError, read_limited, read_limited_at, MAX_MANIFEST_BYTES, MAX_LOG_BYTES,
    MAX_RGBA_BYTES, MAX_RECEIPT_BYTES, MAX_NONCE_BYTES, MAX_EXIT_BYTES,
)

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
    fd = None
    try:
        fd = os.open(nro_file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 20 <= info.st_size <= 16*1024*1024:
            raise SessionError("invalid NRO size or file type")
        data = bytearray()
        while len(data) <= 16*1024*1024:
            chunk = os.read(fd, min(1024*1024, 16*1024*1024 + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if not 20 <= len(data) <= 16*1024*1024:
            raise SessionError("invalid NRO size")
        if data[16:20] != b"NRO0":
            raise SessionError("NRO0 header missing")
        return digest(bytes(data))
    except SessionError:
        raise
    except OSError as exc:
        raise SessionError("NRO must be a readable regular non-symlink file") from exc
    finally:
        if fd is not None:
            os.close(fd)


def sd_dir(root: Path) -> Path:
    return root / "switch" / "heman-stage230"


def _ensure_real_directory(path: Path, *, create: bool = False) -> None:
    """Require the final path component to be a directory, never a symlink."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        if not create:
            raise SessionError("required SD capture directory is missing")
        try:
            path.mkdir()
        except FileExistsError:
            # Another process may have created it; validate the resulting inode.
            pass
        except OSError as exc:
            raise SessionError(
                f"could not create SD capture directory: {type(exc).__name__}"
            ) from exc
        try:
            info = path.lstat()
        except OSError as exc:
            raise SessionError("could not inspect created SD capture directory") from exc
    except OSError as exc:
        raise SessionError(f"could not inspect SD capture directory: {type(exc).__name__}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SessionError("SD capture path components must be non-symlink directories")


def _ensure_sd_capture_dir(sd_root: Path) -> Path:
    """Create/check the SD capture chain one component at a time."""
    try:
        root_info = sd_root.lstat()
    except FileNotFoundError:
        try:
            sd_root.mkdir(parents=True, exist_ok=True)
            root_info = sd_root.lstat()
        except OSError as exc:
            raise SessionError("could not create or inspect SD root") from exc
    except OSError as exc:
        raise SessionError("could not inspect SD root") from exc
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise SessionError("SD root must be a non-symlink directory")

    current = sd_root
    for name in ("switch", "heman-stage230"):
        current = current / name
        _ensure_real_directory(current, create=True)
    return current


def _supports_descriptor_io() -> bool:
    dir_fd = getattr(os, "supports_dir_fd", set())
    fd_ops = getattr(os, "supports_fd", set())
    return bool(
        getattr(os, "O_NOFOLLOW", 0)
        and getattr(os, "O_DIRECTORY", 0)
        and all(op in dir_fd for op in (os.open, os.mkdir, os.unlink, os.rename, os.stat))
        and os.listdir in fd_ops
    )


def _open_directory_path(path: Path, label: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            os.close(fd)
            raise SessionError(f"{label} must be a non-symlink directory")
        return fd
    except SessionError:
        raise
    except OSError as exc:
        raise SessionError(f"{label} must be a readable non-symlink directory") from exc


def _open_sd_capture_dir_fd(sd_root: Path, *, create: bool) -> int:
    """Open and pin each SD path component; no path lookup follows child symlinks."""
    current_fd = None
    try:
        try:
            root_info = sd_root.lstat()
        except FileNotFoundError:
            if not create:
                raise SessionError("required SD capture directory is missing")
            try:
                sd_root.mkdir(parents=True, exist_ok=True)
                root_info = sd_root.lstat()
            except OSError as exc:
                raise SessionError("could not create or inspect SD root") from exc
        except OSError as exc:
            raise SessionError("could not inspect SD root") from exc
        if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
            raise SessionError("SD root must be a non-symlink directory")
        current_fd = _open_directory_path(sd_root, "SD root")
        for name in ("switch", "heman-stage230"):
            try:
                next_fd = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            except FileNotFoundError:
                if not create:
                    raise SessionError("required SD capture directory is missing")
                try:
                    os.mkdir(name, 0o755, dir_fd=current_fd)
                except FileExistsError:
                    pass
                except OSError as exc:
                    raise SessionError("could not create SD capture directory") from exc
                try:
                    next_fd = os.open(
                        name,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=current_fd,
                    )
                except OSError as exc:
                    raise SessionError(
                        "SD capture path components must be non-symlink directories"
                    ) from exc
            except OSError as exc:
                raise SessionError(
                    "SD capture path components must be non-symlink directories"
                ) from exc
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = None
        return result
    finally:
        if current_fd is not None:
            os.close(current_fd)


def _unlink_at(directory_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=directory_fd)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise SessionError(f"could not safely remove stale capture entry: {name}") from exc


def _write_file_at(
    directory_fd: int, name: str, data: bytes, *, exclusive: bool = False
) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    fd = None
    try:
        fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise SessionError(f"refusing non-regular output entry: {name}")
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            written = os.write(fd, view[offset:])
            if written <= 0:
                raise SessionError(f"short write while creating output entry: {name}")
            offset += written
    except SessionError:
        raise
    except OSError as exc:
        raise SessionError(f"could not safely write output entry: {name}") from exc
    finally:
        if fd is not None:
            os.close(fd)


def _entry_exists_at(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise SessionError(f"could not inspect session entry: {name}") from exc


def prepare(nro: Path, sd_root: Path, output_dir: Path, *, challenge: str | None = None) -> dict:
    binary_digest = nro_sha256(nro)
    try:
        output_info = output_dir.lstat()
    except FileNotFoundError:
        output_info = None
    except OSError as exc:
        raise SessionError("could not inspect session output directory") from exc
    if output_info is not None:
        if stat.S_ISLNK(output_info.st_mode) or not stat.S_ISDIR(output_info.st_mode):
            raise SessionError("session output must be a non-symlink directory")
        try:
            if any(output_dir.iterdir()):
                raise SessionError("session output directory is not empty")
        except OSError as exc:
            raise SessionError("could not inspect session output directory contents") from exc
    if challenge is None:
        challenge = secrets.token_hex(16)
    if not NONCE.fullmatch(challenge):
        raise SessionError("challenge must be 128-bit lowercase hex")
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
    stale_names = (
        "readback.rgba", "readback.receipt",
        "readback.rgba.tmp", "readback.receipt.tmp",
        "upload.rgba", "upload.rgba.tmp",
        "gpu_phase.txt", "gpu_phase.tmp",
        "guest_exit.txt", "guest_exit.tmp",
        "run_nonce.txt.tmp",
    )
    manifest_bytes = (json.dumps(request, indent=2, sort_keys=True) + "\n").encode("utf-8")

    if _supports_descriptor_io():
        sd_fd = None
        output_fd = None
        try:
            sd_fd = _open_sd_capture_dir_fd(sd_root, create=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_fd = _open_directory_path(output_dir, "session output")
            if os.listdir(output_fd):
                raise SessionError("session output directory is not empty")
            # Directory descriptors pin the checked inodes; replacing a path
            # with a symlink after open cannot redirect these operations.
            for name in stale_names:
                _unlink_at(sd_fd, name)
            try:
                _write_file_at(
                    sd_fd, "run_nonce.txt.tmp",
                    (challenge + "\n").encode("ascii"), exclusive=True,
                )
                os.rename(
                    "run_nonce.txt.tmp", "run_nonce.txt",
                    src_dir_fd=sd_fd, dst_dir_fd=sd_fd,
                )
            except OSError as exc:
                try:
                    _unlink_at(sd_fd, "run_nonce.txt.tmp")
                except SessionError:
                    pass
                raise SessionError("could not atomically write SD session nonce") from exc
            _write_file_at(output_fd, "stage231_session.json", manifest_bytes, exclusive=True)
        finally:
            if output_fd is not None:
                os.close(output_fd)
            if sd_fd is not None:
                os.close(sd_fd)
    else:
        # Compatibility fallback for platforms without O_NOFOLLOW/dir_fd.
        # Stage253 still gates real launches; this path retains Stage254's
        # repeated lstat checks but cannot pin directories against a racing writer.
        sd = _ensure_sd_capture_dir(sd_root)
        output_dir.mkdir(parents=True, exist_ok=True)
        sd = _ensure_sd_capture_dir(sd_root)
        for name in stale_names:
            (sd / name).unlink(missing_ok=True)
        sd = _ensure_sd_capture_dir(sd_root)
        nonce_tmp = sd / "run_nonce.txt.tmp"
        nonce_final = sd / "run_nonce.txt"
        try:
            nonce_tmp.write_text(challenge + "\n", encoding="ascii")
            os.replace(nonce_tmp, nonce_final)
        except OSError as exc:
            nonce_tmp.unlink(missing_ok=True)
            raise SessionError("could not atomically write SD session nonce") from exc
        (output_dir / "stage231_session.json").write_bytes(manifest_bytes)
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
    manifest_name = "stage231_session.json"
    collected_name = "stage231_collected.json"
    output_fd = None
    sd_fd = None
    descriptor_io = _supports_descriptor_io()
    try:
        if descriptor_io:
            output_fd = _open_directory_path(output_dir, "session output")
            if not _entry_exists_at(output_fd, manifest_name):
                raise SessionError("missing previously prepared session")
            if _entry_exists_at(output_fd, collected_name):
                raise SessionError("session was already collected; create a fresh session")
            sd_fd = _open_sd_capture_dir_fd(sd_root, create=False)
            session_raw = read_limited_at(
                output_fd, manifest_name, MAX_MANIFEST_BYTES, "prepared session manifest"
            )
            session = json.loads(session_raw.decode("utf-8"))
            nonce_text = read_limited_at(
                sd_fd, "run_nonce.txt", MAX_NONCE_BYTES, "SD request nonce"
            ).decode("ascii")
            rgba_bytes = read_limited_at(
                sd_fd, "readback.rgba", MAX_RGBA_BYTES, "GPU readback file"
            )
            receipt_bytes = read_limited_at(
                sd_fd, "readback.receipt", MAX_RECEIPT_BYTES, "completion receipt"
            )
        else:
            manifest = output_dir / manifest_name
            if not manifest.is_file():
                raise SessionError("missing previously prepared session")
            if (output_dir / collected_name).exists():
                raise SessionError("session was already collected; create a fresh session")
            sd = sd_dir(sd_root)
            session = json.loads(read_limited(
                manifest, MAX_MANIFEST_BYTES, "prepared session manifest"
            ).decode("utf-8"))
            nonce_text = read_limited(
                sd / "run_nonce.txt", MAX_NONCE_BYTES, "SD request nonce"
            ).decode("ascii")
            rgba_bytes = read_limited(
                sd / "readback.rgba", MAX_RGBA_BYTES, "GPU readback file"
            )
            receipt_bytes = read_limited(
                sd / "readback.receipt", MAX_RECEIPT_BYTES, "completion receipt"
            )

        status_text = read_limited(
            exit_status_path, MAX_EXIT_BYTES, "exit status"
        ).decode("ascii").strip()
        log_bytes = read_limited(runner_log_path, MAX_LOG_BYTES, "runner log")
        if not re.fullmatch(r"[0-9]{1,3}", status_text):
            raise SessionError("invalid independent exit status")
        if len(rgba_bytes) != BYTES:
            raise SessionError("missing or incorrectly sized GPU readback file")
        result = validate(
            session,
            nonce_text,
            rgba_bytes,
            receipt_bytes.decode("ascii"),
            nro_sha256(nro),
            int(status_text),
            log_bytes,
            runtime,
            command,
        )
        # The POSIX path writes relative to pinned directory descriptors and
        # refuses every pre-existing output entry, including symlinks/hardlinks.
        # This also makes a concurrent second COLLECT fail closed at the marker.
        if descriptor_io:
            outputs = (
                ("readback.rgba", rgba_bytes),
                ("readback.receipt", receipt_bytes),
                ("runtime.log", log_bytes),
                ("exit-status.txt", (status_text + "\n").encode("ascii")),
            )
            for name, data in outputs:
                _write_file_at(output_fd, name, data, exclusive=True)
            _write_file_at(
                output_fd,
                collected_name,
                (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"),
                exclusive=True,
            )
        else:
            (output_dir / "readback.rgba").write_bytes(rgba_bytes)
            (output_dir / "readback.receipt").write_bytes(receipt_bytes)
            (output_dir / "runtime.log").write_bytes(log_bytes)
            (output_dir / "exit-status.txt").write_text(status_text + "\n", encoding="ascii")
            (output_dir / collected_name).write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        return result
    except (EvidenceReadError, UnicodeError, json.JSONDecodeError) as exc:
        raise SessionError(str(exc)) from exc
    finally:
        if sd_fd is not None:
            os.close(sd_fd)
        if output_fd is not None:
            os.close(output_fd)


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
