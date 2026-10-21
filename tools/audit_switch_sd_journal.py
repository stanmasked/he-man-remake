"""Read-only structural audit for He-Man's *synthetic* 120-byte SD journal.

This does not validate original iOS saves, runtime map compatibility, actual
SD flush durability, physical cold-start behavior or cryptographic provenance.
Neither original assets nor save-file contents are uploaded anywhere.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

RECORD_SIZE = 120
SNAPSHOT_SIZE = 96
MASK64 = (1 << 64) - 1
FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211


def fnv64(raw: bytes) -> int:
    result = FNV_OFFSET
    for byte in raw:
        result = ((result ^ byte) * FNV_PRIME) & MASK64
    return result


def invalid(reason: str) -> dict:
    return {"status": "invalid", "reason": reason}


def decode_record(raw: bytes) -> dict:
    """Validate outer/inner portable envelopes, not the live C99 game world."""
    if len(raw) != RECORD_SIZE:
        return invalid("wrong_length")
    if raw[:4] != b"H1J1":
        return invalid("journal_magic")
    if raw[4] != 1:
        return invalid("unsupported_journal_version")
    if raw[5:8] != b"\0" * 3:
        return invalid("journal_reserved")
    generation = struct.unpack_from("<Q", raw, 8)[0]
    if generation == 0:
        return invalid("zero_generation")
    if struct.unpack_from("<Q", raw, 112)[0] != fnv64(raw[:112]):
        return invalid("journal_checksum")
    snap = raw[16:112]
    if snap[:4] != b"H1S1":
        return invalid("snapshot_magic")
    if snap[4:8] != b"\x01\x00\x60\x00":
        return invalid("snapshot_header")
    if snap[85:88] != b"\0" * 3:
        return invalid("snapshot_reserved")
    if struct.unpack_from("<Q", snap, 88)[0] != fnv64(snap[:88]):
        return invalid("snapshot_checksum")
    x, feet_y, vy, camera_x, camera_y = struct.unpack_from("<5f", snap, 28)
    if any(not math.isfinite(v) or abs(v) > 1000000.0
           for v in (x, feet_y, vy, camera_x, camera_y)):
        return invalid("snapshot_float")
    flags = snap[76:82]  # Four physics flags plus two lore booleans.
    mask, count, previous_down = snap[82], snap[83], snap[84]
    if (any(value > 1 for value in flags) or previous_down > 1 or
            mask > 3 or count > 2 or mask.bit_count() != count):
        return invalid("snapshot_state_fields")
    world_seal = struct.unpack_from("<Q", snap, 8)[0]
    bindings = struct.unpack_from("<III", snap, 16)
    frame = struct.unpack_from("<I", snap, 48)[0]
    return {
        "status": "structurally_valid",
        "generation": generation,
        "world_seal": f"{world_seal:016x}",
        "bindings": list(bindings),
        "player_frame": frame,
        "collected_mask": mask,
        "collected_count": count,
        "wall_crusher_unlocked": snap[80] == 1,
        "left_gate_broken": snap[81] == 1,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def inspect_slot(path: Path, slot: int) -> dict:
    """Read at most 121 bytes; do not follow symlinks or mutate the files."""
    if path.is_symlink():
        report = invalid("symlink_disallowed")
    else:
        try:
            with path.open("rb") as stream:
                raw = stream.read(RECORD_SIZE + 1)
        except FileNotFoundError:
            report = {"status": "missing"}
        except OSError:
            report = invalid("unreadable")
        else:
            report = decode_record(raw)
    return {"slot": slot, **report}


def summarize_slots(slots: list[dict]) -> dict:
    """Reuse the same journal ranking/ambiguity rules for path or fd reads."""
    valid = [entry for entry in slots
             if entry["status"] == "structurally_valid"]
    bindings = {(entry["world_seal"], tuple(entry["bindings"]))
                for entry in valid}
    ambiguous = len(bindings) > 1
    latest = None
    if valid and not ambiguous:
        # The native C99 loader also requires an independently valid *live*
        # world, which this offline auditor cannot reconstruct or verify.
        latest = max(valid, key=lambda entry: (entry["generation"], -entry["slot"]))["slot"]
    return {
        "format": "heman-synthetic-stage113-journal-v1",
        "slots": slots,
        "structurally_valid_slot_count": len(valid),
        "ambiguous_world_binding": ambiguous,
        "latest_structural_candidate_slot": latest,
        "runtime_world_compatibility_verified": False,
        "real_sd_commit_or_cold_boot_verified": False,
        "original_ios_data_verified": False,
        "note": "Structural integrity only; FNV-1a is not authentication.",
    }


def audit_directory(directory: Path) -> dict:
    slots = [inspect_slot(directory / f"progress{slot}.bin", slot)
             for slot in (0, 1)]
    return summarize_slots(slots)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path,
                        help="LOCAL directory containing progress0.bin and progress1.bin")
    args = parser.parse_args(argv)
    report = audit_directory(args.directory)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if (report["latest_structural_candidate_slot"] is not None) else 2


if __name__ == "__main__":
    raise SystemExit(main())
