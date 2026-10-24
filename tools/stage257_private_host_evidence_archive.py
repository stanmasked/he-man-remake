#!/usr/bin/env python3
"""Create a private, bounded Stage257 archive after a Stage240 host attempt.

Only whitelisted reports and capture outputs are included. The emulator and NRO
binaries are never copied. This package preserves evidence; it does not attest
that the emulator executed the guest or that a GPU produced the captured bytes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

from stage231_capture_session import (
    _open_directory_path,
    _open_sd_capture_dir_fd,
    _supports_descriptor_io,
    MAX_EXIT_BYTES,
    MAX_LOG_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_NONCE_BYTES,
    MAX_RECEIPT_BYTES,
    MAX_RGBA_BYTES,
)
from stage243_bounded_evidence import EvidenceReadError, read_limited, read_limited_at

MAX_PREFLIGHT_BYTES = 1024 * 1024
MAX_LAUNCH_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024

SESSION_FILES = (
    ("stage240_launch.json", MAX_LAUNCH_BYTES, True),
    ("stage231_session.json", MAX_MANIFEST_BYTES, True),
    ("stage231_collected.json", MAX_MANIFEST_BYTES, False),
    ("stage240_bundle.json", MAX_BUNDLE_BYTES, False),
    ("host-launch.log", MAX_LOG_BYTES, False),
    ("runner-exit-status.txt", MAX_EXIT_BYTES, False),
    ("readback.rgba", MAX_RGBA_BYTES, False),
    ("readback.receipt", MAX_RECEIPT_BYTES, False),
    ("runtime.log", MAX_LOG_BYTES, False),
    ("exit-status.txt", MAX_EXIT_BYTES, False),
)
SD_FILES = (
    ("run_nonce.txt", MAX_NONCE_BYTES),
    ("readback.rgba", MAX_RGBA_BYTES),
    ("readback.receipt", MAX_RECEIPT_BYTES),
    ("guest_exit.txt", MAX_EXIT_BYTES),
    ("gpu_phase.txt", MAX_EXIT_BYTES),
)


class ArchiveError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _inside_git_worktree(path: Path) -> bool:
    current = path.resolve(strict=False)
    for parent in (current, *current.parents):
        marker = parent / ".git"
        if marker.exists() or marker.is_symlink():
            return True
    return False


def _require_directory(path: Path, label: str, *, private: bool = False) -> None:
    if not path.is_absolute():
        raise ArchiveError(f"{label} path must be absolute")
    try:
        info = path.lstat()
    except OSError as exc:
        raise ArchiveError(f"{label} directory is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ArchiveError(f"{label} must be a non-symlink directory")
    if private and os.name != "nt" and (info.st_mode & 0o077):
        raise ArchiveError(f"{label} must be owner-private on POSIX")


def _read_external(path: Path, limit: int, label: str, *, private_parent: bool = False) -> bytes:
    if not path.is_absolute():
        raise ArchiveError(f"{label} path must be absolute")
    try:
        info = path.lstat()
    except OSError as exc:
        raise ArchiveError(f"{label} is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ArchiveError(f"{label} must be a regular non-symlink file")
    if info.st_size > limit:
        raise ArchiveError(f"{label} exceeds the {limit}-byte limit")
    _require_directory(path.parent, f"{label} parent", private=private_parent)
    try:
        return read_limited(path, limit, label)
    except EvidenceReadError as exc:
        raise ArchiveError(str(exc)) from exc


def _read_child(
    directory: Path,
    directory_fd: int | None,
    name: str,
    limit: int,
    label: str,
) -> bytes | None:
    if directory_fd is not None:
        try:
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ArchiveError(f"could not inspect {label}") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ArchiveError(f"{label} must be a regular non-symlink file")
        if info.st_size > limit:
            raise ArchiveError(f"{label} exceeds the {limit}-byte limit")
        try:
            return read_limited_at(directory_fd, name, limit, label)
        except EvidenceReadError as exc:
            raise ArchiveError(str(exc)) from exc

    path = directory / name
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ArchiveError(f"could not inspect {label}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ArchiveError(f"{label} must be a regular non-symlink file")
    if info.st_size > limit:
        raise ArchiveError(f"{label} exceeds the {limit}-byte limit")
    try:
        return read_limited(path, limit, label)
    except EvidenceReadError as exc:
        raise ArchiveError(str(exc)) from exc


def _parse_json(data: bytes, label: str) -> dict:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ArchiveError(f"{label} must contain a JSON object")
    return value


def _validate_evidence(preflight: dict, launch: dict, session: dict, preflight_raw: bytes) -> None:
    if preflight.get("schema") != "heman-stage252-runtime-preflight-v1":
        raise ArchiveError("unexpected Stage252 report schema")
    if preflight.get("result") != "preflight_passed_not_launched":
        raise ArchiveError("Stage252 report did not pass")
    checks = preflight.get("checks")
    if not isinstance(checks, dict) or not checks or any(value is not True for value in checks.values()):
        raise ArchiveError("Stage252 report contains missing or false checks")
    if checks.get("sd_root_mapping_operator_confirmed") is not True:
        raise ArchiveError("Stage252 report lacks explicit SD-root mapping confirmation")
    for key in (
        "emulator_was_launched",
        "sd_root_mapping_independently_verified",
        "runtime_gpu_execution_attested",
        "gpu_capability_independently_verified",
        "original_ios_graphics_parity_attested",
    ):
        if preflight.get(key) is not False:
            raise ArchiveError(f"Stage252 report has an invalid evidence flag: {key}")

    if launch.get("schema") != "stage240-host-emulator-attempt-v1":
        raise ArchiveError("unexpected Stage240 launch manifest schema")
    if launch.get("stage252_preflight_gate_status") != "accepted":
        raise ArchiveError("Stage240 manifest does not record an accepted Stage252 gate")
    gate = launch.get("stage252_preflight_gate")
    report_hash = _sha256(preflight_raw)
    if not isinstance(gate, dict) or gate.get("accepted") is not True:
        raise ArchiveError("Stage240 manifest lacks an accepted preflight gate record")
    if gate.get("stage252_report_sha256") != report_hash:
        raise ArchiveError("Stage252 report hash does not match the Stage240 gate record")
    if launch.get("test_only_runner_declared") is not False:
        raise ArchiveError("test-only runner output cannot be archived as a real host attempt")
    for key in (
        "runtime_gpu_execution_attested",
        "emulator_gpu_capability_independently_verified",
        "guest_process_exit_independently_verified",
    ):
        if launch.get(key) is not False:
            raise ArchiveError(f"Stage240 manifest has an invalid evidence flag: {key}")

    hashes = preflight.get("sha256")
    if not isinstance(hashes, dict):
        raise ArchiveError("Stage252 report lacks file hashes")
    nro_hash = launch.get("nro_sha256")
    emulator_hash = launch.get("emulator_executable_sha256")
    if not isinstance(nro_hash, str) or hashes.get("nro_sha256") != nro_hash:
        raise ArchiveError("NRO hash differs between Stage252 and Stage240")
    if not isinstance(emulator_hash, str) or hashes.get("emulator_sha256") != emulator_hash:
        raise ArchiveError("emulator hash differs between Stage252 and Stage240")
    if gate.get("nro_sha256") != nro_hash or gate.get("emulator_sha256") != emulator_hash:
        raise ArchiveError("preflight gate hashes differ from Stage240 input hashes")

    if session.get("schema") != "stage231-capture-session-v1":
        raise ArchiveError("unexpected Stage231 session manifest schema")
    if session.get("nro_sha256") != nro_hash:
        raise ArchiveError("NRO hash differs between Stage231 and Stage240")
    if session.get("nonce") != launch.get("prepared_session_nonce"):
        raise ArchiveError("session nonce differs between Stage231 and Stage240")
    if session.get("runtime_provenance_attested") is not False:
        raise ArchiveError("Stage231 manifest has an invalid provenance flag")


def _open_sd_capture(sd_root: Path) -> tuple[int | None, Path]:
    if _supports_descriptor_io():
        try:
            return _open_sd_capture_dir_fd(sd_root, create=False), (
                sd_root / "switch" / "heman-stage230"
            )
        except (OSError, ValueError) as exc:
            raise ArchiveError(f"SD capture directory is unsafe or missing: {exc}") from exc

    _require_directory(sd_root, "SD root")
    switch = sd_root / "switch"
    capture = switch / "heman-stage230"
    _require_directory(switch, "SD switch")
    _require_directory(capture, "SD capture")
    return None, capture


def _create_archive(output_path: Path, entries: dict[str, bytes], manifest: dict) -> dict:
    parent_fd = None
    fd = None
    created = False
    try:
        flags = (
            os.O_RDWR | os.O_CREAT | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_BINARY", 0)
        )
        if _supports_descriptor_io():
            parent_fd = os.open(
                output_path.parent,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
            fd = os.open(output_path.name, flags, 0o600, dir_fd=parent_fd)
        else:
            fd = os.open(output_path, flags, 0o600)
        created = True
        with os.fdopen(fd, "w+b", closefd=False) as stream:
            with zipfile.ZipFile(
                stream, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as archive:
                for name in sorted(entries):
                    archive.writestr(name, entries[name])
                archive.writestr(
                    "stage257_archive_manifest.json",
                    (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
                )
            stream.flush()
            os.fsync(fd)
            size = stream.seek(0, os.SEEK_END)
            if size > MAX_ARCHIVE_BYTES:
                raise ArchiveError("archive exceeds the 16 MiB output limit")
            stream.seek(0)
            hasher = hashlib.sha256()
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        return {
            "archive_name": output_path.name,
            "archive_bytes": size,
            "archive_sha256": hasher.hexdigest(),
            "included_file_count": len(entries) + 1,
            "result": "private_host_attempt_archived_not_gpu_attestation",
            "runtime_gpu_execution_attested": False,
            "gpu_capability_independently_verified": False,
            "original_ios_graphics_parity_attested": False,
        }
    except Exception:
        if created:
            try:
                if parent_fd is not None:
                    os.unlink(output_path.name, dir_fd=parent_fd)
                else:
                    output_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        if fd is not None:
            os.close(fd)
        if parent_fd is not None:
            os.close(parent_fd)


def archive_host_evidence(
    preflight_path: Path,
    session_dir: Path,
    sd_root: Path,
    output_path: Path,
) -> dict:
    for path, label in (
        (preflight_path, "Stage252 report"),
        (session_dir, "session output"),
        (sd_root, "SD root"),
        (output_path, "archive output"),
    ):
        if not path.is_absolute():
            raise ArchiveError(f"{label} path must be absolute")

    _require_directory(session_dir, "session output", private=True)
    _require_directory(sd_root, "SD root")
    _require_directory(preflight_path.parent, "Stage252 report parent", private=True)
    _require_directory(output_path.parent, "archive parent", private=True)

    try:
        output_info = output_path.lstat()
    except FileNotFoundError:
        output_info = None
    except OSError as exc:
        raise ArchiveError("could not inspect archive output path") from exc
    if output_info is not None:
        raise ArchiveError("archive output already exists; choose a new name")

    if preflight_path.is_symlink():
        raise ArchiveError("Stage252 report must not be a symlink")
    if output_path == preflight_path:
        raise ArchiveError("archive output must not overwrite the Stage252 report")
    if _is_within(preflight_path, session_dir) or _is_within(preflight_path, sd_root):
        raise ArchiveError("Stage252 report must be outside session and SD directories")
    if _is_within(output_path, session_dir) or _is_within(output_path, sd_root):
        raise ArchiveError("archive output must be outside session and SD directories")
    if _inside_git_worktree(output_path.parent) or _inside_git_worktree(preflight_path.parent):
        raise ArchiveError("private reports and archives must not be stored inside a Git worktree")

    preflight_raw = _read_external(
        preflight_path, MAX_PREFLIGHT_BYTES, "Stage252 report", private_parent=True
    )
    preflight = _parse_json(preflight_raw, "Stage252 report")

    output_fd = None
    sd_fd = None
    entries: dict[str, bytes] = {}
    missing_optional: list[str] = []
    file_records: list[dict] = []
    try:
        if _supports_descriptor_io():
            output_fd = _open_directory_path(session_dir, "session output")
        launch_raw = _read_child(
            session_dir, output_fd, "stage240_launch.json", MAX_LAUNCH_BYTES, "Stage240 launch manifest"
        )
        session_raw = _read_child(
            session_dir, output_fd, "stage231_session.json", MAX_MANIFEST_BYTES, "Stage231 session manifest"
        )
        if launch_raw is None or session_raw is None:
            raise ArchiveError("Stage240 launch and Stage231 session manifests are required")
        launch = _parse_json(launch_raw, "Stage240 launch manifest")
        session = _parse_json(session_raw, "Stage231 session manifest")
        _validate_evidence(preflight, launch, session, preflight_raw)

        entries["stage252_preflight.json"] = preflight_raw
        entries["session/stage240_launch.json"] = launch_raw
        entries["session/stage231_session.json"] = session_raw

        for name, limit, required in SESSION_FILES:
            if name in ("stage240_launch.json", "stage231_session.json"):
                continue
            data = _read_child(session_dir, output_fd, name, limit, f"session/{name}")
            archive_name = f"session/{name}"
            if data is None:
                if required:
                    raise ArchiveError(f"required evidence file is missing: {archive_name}")
                missing_optional.append(archive_name)
                continue
            entries[archive_name] = data

        sd_fd, capture_dir = _open_sd_capture(sd_root)
        for name, limit in SD_FILES:
            data = _read_child(capture_dir, sd_fd, name, limit, f"SD capture/{name}")
            archive_name = f"sd_capture/{name}"
            if data is None:
                missing_optional.append(archive_name)
                continue
            entries[archive_name] = data

        if "session/stage231_collected.json" in entries:
            collected = _parse_json(entries["session/stage231_collected.json"], "Stage231 collection manifest")
            for key in (
                "runtime_gpu_execution_attested",
                "gpu_capability_independently_verified",
                "original_ios_graphics_parity_attested",
            ):
                if collected.get(key) is not False:
                    raise ArchiveError(f"Stage231 collection has an invalid evidence flag: {key}")

        file_records = [
            {"name": name, "size_bytes": len(data), "sha256": _sha256(data)}
            for name, data in sorted(entries.items())
        ]
        launch_gate = launch["stage252_preflight_gate"]
        manifest = {
            "schema": "heman-stage257-private-host-archive-v1",
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "result": "private_host_attempt_archived_not_gpu_attestation",
            "included_files": file_records,
            "missing_optional_files": sorted(missing_optional),
            "preflight_report_sha256": _sha256(preflight_raw),
            "stage240_launch_manifest_sha256": _sha256(launch_raw),
            "nro_sha256": launch["nro_sha256"],
            "emulator_executable_sha256": launch["emulator_executable_sha256"],
            "stage252_gate_age_seconds": launch_gate.get("stage252_report_age_seconds"),
            "host_process_exit_code": launch.get("host_process_exit_code"),
            "host_timed_out": launch.get("host_timed_out"),
            "stage231_collected": launch.get("stage231_collected") is True,
            "stage236_bundle_consistent": launch.get("stage236_bundle_consistent") is True,
            "stage241_guest_exit_receipt_accepted": launch.get("stage241_guest_exit_receipt_accepted") is True,
            "runtime_backend_log_audit_status": launch.get("runtime_backend_log_audit_status"),
            "runtime_gpu_execution_attested": False,
            "gpu_capability_independently_verified": False,
            "original_ios_graphics_parity_attested": False,
            "original_emulator_and_nro_binaries_included": False,
            "note": (
                "The archive preserves a host attempt and bounded evidence files. "
                "It is not a signed attestation and does not prove guest execution or GPU provenance."
            ),
        }
        return _create_archive(output_path, entries, manifest)
    finally:
        if sd_fd is not None:
            os.close(sd_fd)
        if output_fd is not None:
            os.close(output_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-report", type=Path, required=True)
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--sd-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = archive_host_evidence(
            args.preflight_report, args.session_dir, args.sd_root, args.output
        )
    except (ArchiveError, OSError, ValueError) as exc:
        print(f"STAGE257_ARCHIVE_FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
