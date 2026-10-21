#!/usr/bin/env python3
"""Local-only IPA screen pack parity audit: NO game resources are exported.

Checks packaging equality across screen-med and screen-xlarge without
extracting proprietary levels/maps/shapes, publishing paths, hashes or
original bytes. CI must use synthetic in-memory ZIP test fixtures ONLY.
"""
from __future__ import annotations

import argparse
import json
import stat
from pathlib import Path
from zipfile import BadZipFile, ZipFile, ZipInfo

PACKS = ("screen-med", "screen-xlarge")
SECTIONS = {"levels": ".lvl", "maps": ".map", "shapes": ".shape"}
PREFIX = "Payload/MOTU.app"
SPECIAL_DIFFERENCE = ("maps", "gs_background_sky.map")
MAX_MEMBER_BYTES = 8_000_000
MAX_SUM_BYTES = 200_000_000
CHUNK = 64 * 1024


class PrivatePackError(ValueError):
    """Invalid archive or unsafe/contradictory local IPA metadata."""


def _check_member(info: ZipInfo) -> None:
    name = info.filename
    if (not name or "\\" in name or "\x00" in name or
            any(segment in ("", ".", "..") for segment in name.split("/")) or
            info.flag_bits & 1):
        raise PrivatePackError("Unsafe or encrypted ZIP member")
    mode = stat.S_IFMT(info.external_attr >> 16)
    if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise PrivatePackError("Archive contains an unsupported ZIP member type")
    if not info.is_dir() and (info.file_size < 0 or
                              info.file_size > MAX_MEMBER_BYTES):
        raise PrivatePackError("IPA member exceeds read-only size bound")


def _index(z: ZipFile) -> dict[tuple[str, str], dict[str, ZipInfo]]:
    seen: set[str] = set()
    selected: dict[tuple[str, str], dict[str, ZipInfo]] = {
        (pack, section): {} for pack in PACKS for section in SECTIONS
    }
    total = 0
    for info in z.infolist():
        # Directory entries use trailing slash and are not game files.
        parts = info.filename.rstrip("/").split("/")
        if (not info.filename or "\\" in info.filename or
                "\x00" in info.filename or
                any(seg in ("", ".", "..") for seg in parts)):
            raise PrivatePackError("Unsafe ZIP path")
        if info.filename in seen:
            raise PrivatePackError("Duplicate ZIP member name")
        seen.add(info.filename)
        if len(parts) != 5 or parts[:2] != ["Payload", "MOTU.app"]:
            continue
        pack, section, leaf = parts[2:]
        if pack not in PACKS or section not in SECTIONS or info.is_dir():
            continue
        if not leaf.endswith(SECTIONS[section]):
            continue
        _check_member(info)
        total += info.file_size
        if total > MAX_SUM_BYTES:
            raise PrivatePackError("Aggregate metadata-input size exceeds bound")
        selected[(pack, section)][leaf] = info
    return selected


def _same_bytes(z: ZipFile, left: ZipInfo, right: ZipInfo) -> bool:
    if left.file_size != right.file_size:
        # Do not silently treat different sizes as equivalent.
        return False
    identical = True
    with z.open(left) as stream_l, z.open(right) as stream_r:
        while True:
            block_l, block_r = stream_l.read(CHUNK), stream_r.read(CHUNK)
            if block_l != block_r:
                identical = False
            if not block_l and not block_r:
                break
    return identical


def audit_local_ipa(ipa: Path, *, require_ios_v2_baseline: bool = False) -> dict:
    if not ipa.is_file():
        raise PrivatePackError("Local IPA was not found")
    try:
        with ZipFile(ipa, mode="r", allowZip64=True) as z:
            index = _index(z)
            summary = {}
            for section in SECTIONS:
                left = index[(PACKS[0], section)]
                right = index[(PACKS[1], section)]
                common = left.keys() & right.keys()
                identical, differing, other_differences = 0, 0, 0
                named_exception = False
                for name in sorted(common):
                    if _same_bytes(z, left[name], right[name]):
                        identical += 1
                    else:
                        differing += 1
                        if (section, name) == SPECIAL_DIFFERENCE:
                            named_exception = True
                        else:
                            other_differences += 1
                summary[section] = {
                    "paired_count": len(common),
                    "matching_bytes_count": identical,
                    "different_bytes_count": differing,
                    "only_med_count": len(left.keys() - right.keys()),
                    "only_xlarge_count": len(right.keys() - left.keys()),
                    "expected_special_sky_difference": named_exception if section == "maps" else False,
                    "unclassified_difference_count": other_differences,
                }
    except (BadZipFile, EOFError, OSError, RuntimeError) as error:
        raise PrivatePackError("Cannot safely read the local IPA archive") from error
    if require_ios_v2_baseline:
        levels, maps, shapes = (summary[n] for n in ("levels", "maps", "shapes"))
        paired = all(s["only_med_count"] == 0 and s["only_xlarge_count"] == 0
                     for s in (levels, maps, shapes))
        if not (paired and levels["paired_count"] == 39 and
                levels["matching_bytes_count"] == 39 and
                maps["paired_count"] == 214 and
                maps["matching_bytes_count"] == 213 and
                maps["different_bytes_count"] == 1 and
                maps["expected_special_sky_difference"] and
                maps["unclassified_difference_count"] == 0 and
                shapes["paired_count"] == 1 and
                shapes["matching_bytes_count"] == 1):
            raise PrivatePackError("This archive does not match the privately verified iOS v2.0.0 structure")
    return {
        "classification": "local_only_original_ios_screen_pack_comparison",
        "pack_a": "screen-med",
        "pack_b": "screen-xlarge",
        "sections": summary,
        "raw_original_bytes_in_report": False,
        "private_level_file_paths_in_report": False,
        "individual_file_hashes_in_report": False,
        "original_gameplay_mechanics_verified": False,
        "original_level_collision_semantics_verified": False,
        "switch_runtime_parity_verified": False,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", type=Path, required=True, help="Local/private original IPA (never uploaded)")
    ap.add_argument("--strict-v2", action="store_true",
                    help="Reject archive if paired metadata differs from known iOS v2.0.0 baseline")
    ap.add_argument("--out", type=Path,
                    help="LOCAL ignored JSON report, e.g. local_reports/screen_parity.json")
    args = ap.parse_args(argv)
    report = audit_local_ipa(args.ipa, require_ios_v2_baseline=args.strict_v2)
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print("Private archive comparison complete. Local aggregate-only report written.")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
