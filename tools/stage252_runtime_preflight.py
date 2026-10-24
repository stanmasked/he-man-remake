#!/usr/bin/env python3
"""Stage252 read-only preflight for a future owner-private Stage240 launch.

This program inspects paths and launch arguments but never starts the emulator,
creates a session, writes to the SD root, or attests GPU execution.
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

MAX_NRO_BYTES = 16 * 1024 * 1024
MIN_NRO_BYTES = 20


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private_mode(path: Path) -> bool | None:
    """Return None on Windows where stdlib cannot verify ACL privacy."""
    if os.name == "nt":
        return None
    return stat.S_IMODE(path.stat().st_mode) & 0o077 == 0


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _sd_capture_directory_chain_safe(root: Path) -> bool:
    """Existing switch/heman-stage230 components must be real directories, not symlinks."""
    if not root.is_absolute():
        return False
    current = root
    for name in ("switch", "heman-stage230"):
        current = current / name
        try:
            info = current.lstat()
        except FileNotFoundError:
            return True
        except OSError:
            return False
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            return False
    return True


def _path_fingerprint(path: Path) -> str | None:
    """Hash a normalized path identity without exposing the absolute path."""
    if not path.is_absolute():
        return None
    try:
        normalized = os.path.normcase(str(path.resolve(strict=False)))
    except OSError:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def preflight(
    emulator: Path,
    nro: Path,
    sd_root: Path,
    session_dir: Path,
    launch_args: list[str],
    *,
    sd_root_mapping_confirmed: bool = False,
) -> dict:
    checks: dict[str, bool] = {}
    notes: list[str] = []
    hashes: dict[str, str | None] = {"emulator_sha256": None, "nro_sha256": None}
    metadata: dict[str, object] = {
        "emulator_name": emulator.name,
        "nro_name": nro.name,
        "sd_root_name": sd_root.name,
        "session_dir_name": session_dir.name,
        "launch_argument_count": len(launch_args),
        "nro_placeholder_count": launch_args.count("{nro}"),
    }

    # Check supplied paths without following symlinks.
    checks["all_input_paths_absolute"] = all(
        p.is_absolute() for p in (emulator, nro, sd_root, session_dir)
    )
    if not checks["all_input_paths_absolute"]:
        notes.append("All input paths must be absolute.")

    emulator_info = None
    if emulator.is_absolute():
        try:
            emulator_info = emulator.lstat()
        except OSError:
            pass
    checks["emulator_regular_non_symlink"] = bool(
        emulator_info is not None
        and stat.S_ISREG(emulator_info.st_mode)
        and not stat.S_ISLNK(emulator_info.st_mode)
    )
    checks["emulator_executable"] = bool(
        checks["emulator_regular_non_symlink"] and os.access(emulator, os.X_OK)
    )
    if checks["emulator_regular_non_symlink"] and checks["emulator_executable"]:
        try:
            hashes["emulator_sha256"] = sha256_file(emulator)
        except OSError:
            checks["emulator_executable"] = False
            notes.append("The emulator file could not be read for hashing.")
    else:
        notes.append("The emulator must be an existing executable regular file, not a symlink.")

    nro_info = None
    if nro.is_absolute():
        try:
            nro_info = nro.lstat()
        except OSError:
            pass
    checks["nro_regular_non_symlink"] = bool(
        nro_info is not None
        and stat.S_ISREG(nro_info.st_mode)
        and not stat.S_ISLNK(nro_info.st_mode)
    )
    nro_header_ok = False
    nro_size_ok = False
    if checks["nro_regular_non_symlink"]:
        nro_size_ok = MIN_NRO_BYTES <= nro_info.st_size <= MAX_NRO_BYTES
        if nro_size_ok:
            try:
                with nro.open("rb") as stream:
                    stream.seek(16)
                    nro_header_ok = stream.read(4) == b"NRO0"
                hashes["nro_sha256"] = sha256_file(nro)
            except OSError:
                notes.append("The NRO could not be read for header/hash checks.")
    checks["nro_size_in_range"] = nro_size_ok
    checks["nro0_header_valid"] = nro_header_ok
    if not checks["nro_regular_non_symlink"] or not nro_size_ok or not nro_header_ok:
        notes.append("The NRO must be a non-symlink regular file, 20 bytes–16 MiB, with NRO0 at offset 16.")

    sd_info = None
    if sd_root.is_absolute():
        try:
            sd_info = sd_root.lstat()
        except OSError:
            pass
    checks["sd_root_existing_non_symlink_directory"] = bool(
        sd_info is not None
        and stat.S_ISDIR(sd_info.st_mode)
        and not stat.S_ISLNK(sd_info.st_mode)
    )
    checks["sd_root_writable"] = bool(
        checks["sd_root_existing_non_symlink_directory"]
        and os.access(sd_root, os.W_OK | os.X_OK)
    )
    checks["sd_capture_directory_chain_safe"] = bool(
        checks["sd_root_existing_non_symlink_directory"]
        and _sd_capture_directory_chain_safe(sd_root)
    )
    if not checks["sd_root_existing_non_symlink_directory"]:
        notes.append("The SD root must be an existing directory, not a symlink.")
    elif not checks["sd_root_writable"]:
        notes.append("The SD root is not writable/searchable by the current user.")
    if not checks["sd_capture_directory_chain_safe"]:
        notes.append("Existing switch/heman-stage230 path components must be real directories, not symlinks or files.")
    checks["sd_root_mapping_operator_confirmed"] = bool(sd_root_mapping_confirmed)
    if not sd_root_mapping_confirmed:
        notes.append("Confirm manually that this exact directory is the emulator's mapped sdmc root.")

    session_exists = False
    session_info = None
    if session_dir.is_absolute():
        try:
            session_info = session_dir.lstat()
            session_exists = True
        except FileNotFoundError:
            pass
        except OSError:
            pass
    session_ok = False
    session_mode: bool | None = None
    if session_exists and session_info is not None:
        session_ok = stat.S_ISDIR(session_info.st_mode) and not stat.S_ISLNK(session_info.st_mode)
        if session_ok:
            try:
                session_ok = not any(session_dir.iterdir())
            except OSError:
                session_ok = False
            if session_ok:
                session_mode = _private_mode(session_dir)
                if session_mode is False:
                    session_ok = False
                    notes.append("The existing session directory has group/world permissions; restrict it to the owner.")
                elif session_mode is None:
                    notes.append("Windows ACL privacy is not inspected by this standard-library preflight.")
    else:
        parent = session_dir.parent
        try:
            parent_info = parent.lstat()
            session_ok = (
                parent.is_absolute()
                and stat.S_ISDIR(parent_info.st_mode)
                and not stat.S_ISLNK(parent_info.st_mode)
                and os.access(parent, os.W_OK | os.X_OK)
            )
            if session_ok:
                session_mode = _private_mode(parent)
                if session_mode is False:
                    session_ok = False
                    notes.append("The session parent has group/world permissions; use an owner-private parent.")
                elif session_mode is None:
                    notes.append("Windows ACL privacy is not inspected by this standard-library preflight.")
        except OSError:
            session_ok = False
    checks["session_target_fresh_and_private"] = session_ok
    if not session_ok:
        notes.append("Session output must be a fresh empty directory or a new child of an owner-private writable directory.")

    # Keep all paths separate; the session must not contaminate the SD tree or inputs.
    separation_ok = False
    try:
        e = emulator.resolve(strict=True)
        n = nro.resolve(strict=True)
        s = sd_root.resolve(strict=True)
        out = session_dir.resolve(strict=False)
        separation_ok = (
            e != n
            and not _is_within(out, s)
            and not _is_within(s, out)
            and not _is_within(e, s)
            and not _is_within(n, s)
            and not _is_within(e, out)
            and not _is_within(n, out)
        )
    except OSError:
        separation_ok = False
    checks["input_and_output_paths_separated"] = separation_ok
    if not separation_ok:
        notes.append("Emulator, NRO, SD root and session output paths must not overlap.")

    args_ok = (
        bool(launch_args)
        and len(launch_args) <= 40
        and launch_args.count("{nro}") == 1
        and all(isinstance(arg, str) and bool(arg) and "\x00" not in arg for arg in launch_args)
        and all("{nro}" not in arg or arg == "{nro}" for arg in launch_args)
    )
    checks["launch_argument_template_valid"] = args_ok
    if not args_ok:
        notes.append("Launch arguments must contain exactly one standalone {nro} placeholder and no empty/NUL arguments.")

    all_passed = all(checks.values())
    if os.name == "nt" and session_mode is None:
        metadata["session_acl_status"] = "not_inspected_by_python_standard_library"
    else:
        metadata["session_acl_status"] = "owner_only_mode" if session_mode is True else (
            "not_applicable_or_not_confirmed" if session_mode is None else "not_owner_only"
        )
    return {
        "schema": "heman-stage252-runtime-preflight-v1",
        "result": "preflight_passed_not_launched" if all_passed else "preflight_blocked",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "checks": checks,
        "input_metadata": metadata,
        "sha256": hashes,
        "path_fingerprints": {
            "emulator_path_sha256": _path_fingerprint(emulator),
            "nro_path_sha256": _path_fingerprint(nro),
            "sd_root_path_sha256": _path_fingerprint(sd_root),
            "session_dir_path_sha256": _path_fingerprint(session_dir),
            "launch_args_sha256": hashlib.sha256(
                json.dumps(launch_args, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
        "sd_root_mapping_independently_verified": False,
        "emulator_was_launched": False,
        "runtime_gpu_execution_attested": False,
        "gpu_capability_independently_verified": False,
        "original_ios_graphics_parity_attested": False,
        "notes": notes,
        "evidence_boundary": (
            "This preflight checks local path properties only. The mapped SD root is an operator assertion, "
            "and a passing preflight does not execute the emulator, guest NRO, or GPU."
        ),
    }


def write_report(path: Path, serialized: str, *, allow_public_output_for_synthetic_ci: bool = False) -> None:
    """Create a new report without overwriting evidence; default to private POSIX parent."""
    if not path.is_absolute():
        raise ValueError("output report path must be absolute")
    if path.is_symlink():
        raise ValueError("output report path must not be a symlink")
    if path.exists():
        raise ValueError("output report already exists; choose a new path to preserve prior evidence")
    parent = path.parent
    try:
        parent_info = parent.lstat()
    except OSError as exc:
        raise ValueError("output report parent must already exist") from exc
    if not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode):
        raise ValueError("output report parent must be a non-symlink directory")
    if os.name != "nt" and _private_mode(parent) is False and not allow_public_output_for_synthetic_ci:
        raise ValueError("output report parent must be owner-private on POSIX")
    # O_EXCL prevents accidental overwrite of a prior report or a race-created file.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(serialized)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--nro", type=Path, required=True)
    parser.add_argument("--sd-root", type=Path, required=True)
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument(
        "--confirm-sd-root-mapping",
        action="store_true",
        help="operator assertion that this exact directory is the emulator's mapped sdmc root",
    )
    parser.add_argument("--output", type=Path, help="optional owner-private JSON report path")
    parser.add_argument(
        "--allow-public-output-for-synthetic-ci",
        action="store_true",
        help="allow a non-private output parent only for synthetic public CI fixtures",
    )
    parser.add_argument("launch_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    launch_args = args.launch_args[1:] if args.launch_args[:1] == ["--"] else args.launch_args
    report = preflight(
        args.emulator,
        args.nro,
        args.sd_root,
        args.session_dir,
        launch_args,
        sd_root_mapping_confirmed=args.confirm_sd_root_mapping,
    )
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    try:
        if args.output is not None:
            if args.output.resolve() == args.sd_root.resolve() or _is_within(
                args.output.resolve(), args.sd_root.resolve()
            ):
                raise ValueError("output report must not be written to the SD root")
            if args.output.resolve() == args.session_dir.resolve() or _is_within(
                args.output.resolve(), args.session_dir.resolve()
            ):
                raise ValueError("output report must not be written into the session directory")
            write_report(
                args.output,
                serialized,
                allow_public_output_for_synthetic_ci=args.allow_public_output_for_synthetic_ci,
            )
    except (OSError, ValueError) as exc:
        print(f"STAGE252_OUTPUT_FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(serialized, end="")
    return 0 if report["result"] == "preflight_passed_not_launched" else 2


if __name__ == "__main__":
    raise SystemExit(main())
