#!/usr/bin/env python3
"""Stage253 gate: bind a recent Stage252 preflight to the exact Stage240 inputs."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat

MAX_REPORT_BYTES = 64 * 1024
DEFAULT_MAX_AGE_SECONDS = 30 * 60
FUTURE_CLOCK_SKEW_SECONDS = 30

REQUIRED_CHECKS = {
    "all_input_paths_absolute",
    "emulator_regular_non_symlink",
    "emulator_executable",
    "nro_regular_non_symlink",
    "nro_size_in_range",
    "nro0_header_valid",
    "sd_root_existing_non_symlink_directory",
    "sd_root_writable",
    "sd_capture_directory_chain_safe",
    "sd_root_mapping_operator_confirmed",
    "session_target_fresh_and_private",
    "input_and_output_paths_separated",
    "launch_argument_template_valid",
}


class PreflightGateError(ValueError):
    """A Stage252 report is missing, stale, or mismatched with launch inputs."""


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _path_fingerprint(path: Path) -> str:
    if not path.is_absolute():
        raise PreflightGateError("all launch paths must be absolute")
    try:
        normalized = os.path.normcase(str(path.resolve(strict=False)))
    except OSError as exc:
        raise PreflightGateError("could not normalize a launch path") from exc
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _sd_capture_directory_chain_safe(root: Path) -> bool:
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PreflightGateError(f"could not hash input file: {type(exc).__name__}") from exc
    return digest.hexdigest()


def _regular_non_symlink(path: Path) -> os.stat_result:
    if not path.is_absolute():
        raise PreflightGateError("input path is not absolute")
    try:
        info = path.lstat()
    except OSError as exc:
        raise PreflightGateError(f"input path unavailable: {type(exc).__name__}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PreflightGateError("input must be a regular non-symlink file")
    return info


def _load_report(path: Path) -> tuple[dict, bytes]:
    if not path.is_absolute():
        raise PreflightGateError("preflight report path must be absolute")
    try:
        info = path.lstat()
    except OSError as exc:
        raise PreflightGateError(f"preflight report unavailable: {type(exc).__name__}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PreflightGateError("preflight report must be a regular non-symlink file")
    if info.st_size > MAX_REPORT_BYTES:
        raise PreflightGateError(f"preflight report exceeds {MAX_REPORT_BYTES} bytes")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PreflightGateError(f"preflight report unreadable: {type(exc).__name__}") from exc
    if len(raw) > MAX_REPORT_BYTES:
        raise PreflightGateError(f"preflight report exceeds {MAX_REPORT_BYTES} bytes")
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightGateError("preflight report is not valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise PreflightGateError("preflight report must be a JSON object")
    return report, raw


def validate_preflight_report(
    report_path: Path,
    emulator: Path,
    nro: Path,
    sd_root: Path,
    session_dir: Path,
    launch_args: list[str],
    *,
    now: dt.datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict:
    """Validate the report against current files, path identities and arguments."""
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 24 * 60 * 60:
        raise PreflightGateError("max preflight age must be between 1 and 86400 seconds")

    report, raw = _load_report(report_path)
    try:
        report_real = report_path.resolve(strict=True)
        sd_real = sd_root.resolve(strict=True)
        session_real = session_dir.resolve(strict=False)
    except OSError as exc:
        raise PreflightGateError("could not normalize report/SD/session paths") from exc
    if _is_within(report_real, sd_real):
        raise PreflightGateError("preflight report must not be stored inside the SD root")
    if _is_within(report_real, session_real):
        raise PreflightGateError("preflight report must not be stored inside the launch session")

    if report.get("schema") != "heman-stage252-runtime-preflight-v1":
        raise PreflightGateError("unexpected Stage252 report schema")
    if report.get("result") != "preflight_passed_not_launched":
        raise PreflightGateError("Stage252 preflight did not pass")
    checks = report.get("checks")
    if not isinstance(checks, dict) or set(checks) != REQUIRED_CHECKS:
        raise PreflightGateError("Stage252 report has missing or unexpected checks")
    if any(value is not True for value in checks.values()):
        raise PreflightGateError("one or more Stage252 preflight checks are false")
    if checks.get("sd_root_mapping_operator_confirmed") is not True:
        raise PreflightGateError("mapped SD root was not explicitly confirmed by the operator")

    # A preflight must not claim it launched or independently proved the guest/GPU.
    for key in (
        "emulator_was_launched",
        "sd_root_mapping_independently_verified",
        "runtime_gpu_execution_attested",
        "gpu_capability_independently_verified",
        "original_ios_graphics_parity_attested",
    ):
        if report.get(key) is not False:
            raise PreflightGateError(f"unexpected evidence claim in Stage252 report: {key}")

    metadata = report.get("input_metadata")
    if not isinstance(metadata, dict):
        raise PreflightGateError("Stage252 report lacks input metadata")
    expected_names = {
        "emulator_name": emulator.name,
        "nro_name": nro.name,
        "sd_root_name": sd_root.name,
        "session_dir_name": session_dir.name,
    }
    for key, value in expected_names.items():
        if metadata.get(key) != value:
            raise PreflightGateError(f"Stage252 input mismatch: {key}")

    fingerprints = report.get("path_fingerprints")
    expected_fingerprints = {
        "emulator_path_sha256": _path_fingerprint(emulator),
        "nro_path_sha256": _path_fingerprint(nro),
        "sd_root_path_sha256": _path_fingerprint(sd_root),
        "session_dir_path_sha256": _path_fingerprint(session_dir),
        "launch_args_sha256": hashlib.sha256(
            json.dumps(launch_args, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    if not isinstance(fingerprints, dict):
        raise PreflightGateError("Stage252 report lacks path fingerprints")
    if fingerprints != expected_fingerprints:
        raise PreflightGateError("Stage252 report path or launch-argument fingerprint mismatch")

    emulator_info = _regular_non_symlink(emulator)
    if not os.access(emulator, os.X_OK):
        raise PreflightGateError("emulator is not executable")
    nro_info = _regular_non_symlink(nro)

    try:
        sd_info = sd_root.lstat()
    except OSError as exc:
        raise PreflightGateError("SD root is unavailable") from exc
    if stat.S_ISLNK(sd_info.st_mode) or not stat.S_ISDIR(sd_info.st_mode):
        raise PreflightGateError("SD root must be a non-symlink directory")
    if not os.access(sd_root, os.W_OK | os.X_OK):
        raise PreflightGateError("SD root is not writable/searchable by the current user")

    if not _sd_capture_directory_chain_safe(sd_root):
        raise PreflightGateError("existing switch/heman-stage230 path components must be non-symlink directories")

    # Recheck session freshness/privacy immediately before Stage240 PREPARE.
    try:
        session_info = session_dir.lstat()
        session_exists = True
    except FileNotFoundError:
        session_info = None
        session_exists = False
    except OSError as exc:
        raise PreflightGateError("session target cannot be inspected") from exc
    if session_exists:
        if (session_info is None or stat.S_ISLNK(session_info.st_mode)
                or not stat.S_ISDIR(session_info.st_mode)):
            raise PreflightGateError("session target must be a non-symlink directory")
        try:
            if any(session_dir.iterdir()):
                raise PreflightGateError("session target is no longer empty")
        except OSError as exc:
            raise PreflightGateError("session target cannot be listed") from exc
        privacy_target = session_dir
    else:
        privacy_target = session_dir.parent
        try:
            parent_info = privacy_target.lstat()
        except OSError as exc:
            raise PreflightGateError("session parent is unavailable") from exc
        if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
            raise PreflightGateError("session parent must be a non-symlink directory")
        if not os.access(privacy_target, os.W_OK | os.X_OK):
            raise PreflightGateError("session parent is not writable/searchable")
    if os.name != "nt" and (privacy_target.stat().st_mode & 0o077):
        raise PreflightGateError("session path is not owner-private on POSIX")

    try:
        emulator_real = emulator.resolve(strict=True)
        nro_real = nro.resolve(strict=True)
    except OSError as exc:
        raise PreflightGateError("could not normalize input paths") from exc
    if (_is_within(emulator_real, sd_real) or _is_within(nro_real, sd_real)
            or _is_within(session_real, sd_real) or _is_within(sd_real, session_real)
            or _is_within(emulator_real, session_real)
            or _is_within(nro_real, session_real)):
        raise PreflightGateError("launch input/output paths overlap")
    if not 20 <= nro_info.st_size <= 16 * 1024 * 1024:
        raise PreflightGateError("NRO size is outside the Stage231 bounds")
    try:
        with nro.open("rb") as stream:
            stream.seek(16)
            if stream.read(4) != b"NRO0":
                raise PreflightGateError("NRO0 header missing from current NRO")
    except OSError as exc:
        raise PreflightGateError("could not read current NRO header") from exc

    reported_hashes = report.get("sha256")
    if not isinstance(reported_hashes, dict):
        raise PreflightGateError("Stage252 report lacks file hashes")
    emulator_sha = _sha256_file(emulator)
    nro_sha = _sha256_file(nro)
    if reported_hashes.get("emulator_sha256") != emulator_sha:
        raise PreflightGateError("emulator file changed after preflight")
    if reported_hashes.get("nro_sha256") != nro_sha:
        raise PreflightGateError("NRO file changed after preflight")

    try:
        created = dt.datetime.fromisoformat(report["created_utc"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PreflightGateError("Stage252 timestamp is missing or invalid") from exc
    if created.tzinfo is None:
        raise PreflightGateError("Stage252 timestamp must include a timezone")
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        raise PreflightGateError("gate comparison time must include a timezone")
    age = (current.astimezone(dt.timezone.utc) - created.astimezone(dt.timezone.utc)).total_seconds()
    if age < -FUTURE_CLOCK_SKEW_SECONDS:
        raise PreflightGateError("Stage252 report timestamp is in the future")
    if age > max_age_seconds:
        raise PreflightGateError("Stage252 preflight report is stale; rerun preflight")

    return {
        "accepted": True,
        "schema": "heman-stage253-preflight-launch-gate-v1",
        "stage252_report_sha256": hashlib.sha256(raw).hexdigest(),
        "stage252_report_created_utc": created.astimezone(dt.timezone.utc).isoformat(),
        "stage252_report_age_seconds": max(0, int(age)),
        "emulator_sha256": emulator_sha,
        "nro_sha256": nro_sha,
        "path_fingerprints_matched": True,
        "launch_argument_fingerprint_matched": True,
        "sd_root_mapping_operator_confirmed": True,
        "sd_root_mapping_independently_verified": False,
        "runtime_gpu_execution_attested": False,
        "original_ios_graphics_parity_attested": False,
        "note": (
            "This gate binds a recent preflight to launch inputs. The report is not signed, "
            "operator SD mapping is not independently verified, and no emulator/GPU execution is attested."
        ),
    }
