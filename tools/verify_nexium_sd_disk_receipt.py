#!/usr/bin/env python3
"""Verify actual *emulator sandbox* SD bytes after a green guest HUD.

Read-only test evidence: no physical Switch durability, independent process
cold boot, or NeXium guest FS/FSP sandbox guarantees are inferred.
Directory components and leaf slots are opened relative to trusted dir fds,
with O_NOFOLLOW, rather than resolving host paths after a separate lstat.
"""
import argparse
import errno
import json
import os
import stat
from contextlib import ExitStack
from pathlib import Path

from audit_switch_sd_journal import RECORD_SIZE, decode_record, invalid, summarize_slots


def _directory_problem(parent_fd: int, part: str) -> str:
    """Classify an unsafe entry; the actual open itself is always NOFOLLOW."""
    try:
        mode = os.stat(part, dir_fd=parent_fd, follow_symlinks=False).st_mode
    except OSError:
        return "unreadable_sd_directory"
    if stat.S_ISLNK(mode):
        return "symlinked_sd_directory_disallowed"
    if not stat.S_ISDIR(mode):
        return "non_directory_sd_component"
    return "unreadable_sd_directory"


def _inspect_slot_fd(lab_fd: int, slot: int) -> dict:
    """Read <=121 bytes, without path re-resolution, aliasing or FIFO hangs."""
    name = f"progress{slot}.bin"
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(name, flags, dir_fd=lab_fd)
    except FileNotFoundError:
        return {"slot": slot, "status": "missing"}
    except OSError as exc:
        try:
            is_link = stat.S_ISLNK(
                os.stat(name, dir_fd=lab_fd, follow_symlinks=False).st_mode
            )
        except OSError:
            is_link = exc.errno == errno.ELOOP
        return {"slot": slot, **invalid("symlink_disallowed" if is_link else "unreadable")}
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            result = invalid("non_regular_file")
        elif info.st_nlink != 1:
            # Reject hardlink aliases into other directories as well.
            result = invalid("hardlinked_file_disallowed")
        else:
            chunks = []
            remaining = RECORD_SIZE + 1
            while remaining:
                data = os.read(fd, remaining)
                if not data:
                    break
                chunks.append(data)
                remaining -= len(data)
            result = decode_record(b"".join(chunks))
    except OSError:
        result = invalid("unreadable")
    finally:
        os.close(fd)
    return {"slot": slot, **result}


def _missing_disk() -> dict:
    return summarize_slots([{"slot": slot, "status": "missing"} for slot in (0, 1)])


def audit_confined_sd(data_root: Path) -> tuple[dict, str | None]:
    """Never follow symlinked parents, including ancestors of data_root.

    Each child is opened relative to the already-open parent fd and retained
    until inspection finishes. This is a read-only host-side auditor, not a
    replacement for NeXium guest FS/FSP directory confinement.
    """
    if not data_root.is_absolute():
        return _missing_disk(), "relative_data_root_disallowed"
    if ".." in data_root.parts:
        return _missing_disk(), "parent_traversal_disallowed"
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        return _missing_disk(), "secure_directory_open_unavailable"

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    flags |= getattr(os, "O_CLOEXEC", 0)
    # Start from the filesystem root, not a path-based open of data_root:
    # even a symlink in /prefix/above/data_root is rejected.
    components = list(data_root.parts[1:]) + ["sdmc", "switch", "heman_lore_lab"]
    try:
        with ExitStack() as stack:
            parent = os.open("/", flags)
            stack.callback(os.close, parent)
            for part in components:
                try:
                    fd = os.open(part, flags, dir_fd=parent)
                except FileNotFoundError:
                    return _missing_disk(), None
                except OSError:
                    return _missing_disk(), _directory_problem(parent, part)
                stack.callback(os.close, fd)
                parent = fd
            disk = summarize_slots([_inspect_slot_fd(parent, slot) for slot in (0, 1)])
            return disk, None
    except OSError:
        return _missing_disk(), "unreadable_sd_directory"


def verify_runtime_receipt(data_root: Path, guest_report: dict) -> tuple[dict, bool]:
    disk, problem = audit_confined_sd(data_root)
    if problem:
        # Unsafe or unsupported directory access is NEVER disk evidence.
        disk = {
            "slots": [{"slot": i, "status": "invalid", "reason": problem}
                      for i in (0, 1)],
            "structurally_valid_slot_count": 0,
            "latest_structural_candidate_slot": None,
            "ambiguous_world_binding": False,
        }
    save_claim = guest_report.get("guest_sd_save_succeeded") is True
    load_claim = guest_report.get("guest_sd_load_succeeded") is True
    round_trip = guest_report.get("guest_sd_round_trip_verified") is True
    valid = disk["structurally_valid_slot_count"] > 0
    candidate = disk["latest_structural_candidate_slot"]
    has_usable_record = valid and candidate is not None
    inconsistent_claim = round_trip and not (save_claim and load_claim)
    missing_disk_proof = (save_claim or load_claim or round_trip) and not has_usable_record
    success = problem is None and not (inconsistent_claim or missing_disk_proof)
    if problem:
        classification = "unsafe_emulator_sd_directory"
    elif inconsistent_claim:
        classification = "inconsistent_guest_optical_claim"
    elif missing_disk_proof:
        classification = "green_guest_hud_without_structurally_valid_sd_file"
    elif round_trip:
        classification = "guest_optical_round_trip_with_structural_emulator_sd_bytes"
    elif save_claim or load_claim:
        classification = "some_guest_sd_operation_with_structural_emulator_sd_bytes"
    else:
        classification = "no_guest_sd_success_claim"
    receipt = {
        "classification": classification,
        "guest_sd_save_succeeded": save_claim,
        "guest_sd_load_succeeded": load_claim,
        "guest_sd_round_trip_verified": round_trip,
        "emulator_sd_slots": disk["slots"],
        "emulator_sd_structurally_valid_slot_count": disk["structurally_valid_slot_count"],
        "emulator_sd_latest_structural_candidate_slot": candidate,
        "emulator_sd_world_ambiguous": disk["ambiguous_world_binding"],
        "emulator_sd_directory_validation": problem or "secure_fd_relative_inspection",
        "actual_emulator_file_bytes_examined": has_usable_record,
        "independent_process_cold_restart_verified": False,
        "nintendo_switch_hardware_sd_verified": False,
        "physical_power_loss_atomicity_verified": False,
    }
    return receipt, success


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path,
                        help="isolated absolute NEXIUM_DATA_ROOT for this CI run")
    parser.add_argument("--guest-report", required=True, type=Path,
                        help="real guest PNG oracle JSON")
    parser.add_argument("--out", required=True, type=Path,
                        help="metadata-only JSON receipt, not raw files")
    args = parser.parse_args(argv)
    with args.guest_report.open(encoding="utf-8") as file:
        guest = json.load(file)
    receipt, okay = verify_runtime_receipt(args.data_root, guest)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(f"STAGE114_EMULATED_DISK_RECEIPT_{'PASS' if okay else 'FAIL'}: "
          f"{receipt['classification']}")
    return 0 if okay else 2


if __name__ == "__main__":
    raise SystemExit(main())
