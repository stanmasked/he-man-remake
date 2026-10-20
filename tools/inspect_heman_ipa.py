"""Metadata-only local inventory for a user's own He-Man iOS IPA.

No extraction, network access, or upload. The JSON contains aggregate counts,
not asset bytes, artwork, script contents, or individual resource filenames.
Run only on a privately stored original archive; NEVER commit the archive.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import plistlib
import stat
import zipfile

MAX_MEMBERS = 100_000
MAX_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_PLIST_SIZE = 2 * 1024 * 1024
VARIANTS = ("screen-med", "screen-xlarge")
RESOURCE_TYPES = (
    ".png", ".lvl", ".map", ".tileset", ".shape", ".skel2d",
    ".skeleton2d", ".ps2d", ".ui", ".caf", ".wad", ".datatable",
    ".repo", ".spline", ".hfnt",
)


class InventoryError(ValueError):
    """Malformed or unsafe archive; never produce partial inventory."""


def _safe_member(member: zipfile.ZipInfo) -> None:
    name = member.filename
    if not name or name.startswith("/") or "\\" in name or "\x00" in name:
        raise InventoryError("unsafe ZIP member path")
    if any(part in ("..", ".") for part in name.split("/")):
        raise InventoryError("ZIP contains a traversal member")
    if stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK:
        raise InventoryError("ZIP contains symbolic links")
    if member.file_size < 0:
        raise InventoryError("invalid member size")


def inspect_ipa(source: Path, *, check_crc: bool = False) -> dict:
    """Inspect existing ZIP directly; no original files are extracted."""
    if not source.is_file() or not zipfile.is_zipfile(source):
        raise InventoryError("not a readable iOS IPA ZIP archive")
    try:
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > MAX_MEMBERS:
                raise InventoryError("unreasonable ZIP member count")
            file_members = [m for m in members if not m.is_dir()]
            total = 0
            observed_names = set()
            for item in members:
                _safe_member(item)
                if item.filename in observed_names:
                    raise InventoryError("duplicate ZIP entry")
                observed_names.add(item.filename)
                if item.flag_bits & 1:
                    raise InventoryError("encrypted ZIP entry")
                total += item.file_size
                if total > MAX_TOTAL_UNCOMPRESSED:
                    raise InventoryError("ZIP exceeds inventory size limit")
            if check_crc and archive.testzip() is not None:
                raise InventoryError("ZIP CRC integrity failure")
            apps = sorted({name.split("/")[1] for name in observed_names
                           if name.startswith("Payload/")
                           and len(name.split("/")) > 2
                           and name.split("/")[1].endswith(".app")})
            if len(apps) != 1:
                raise InventoryError("expected one iOS .app bundle")
            app_prefix = "Payload/" + apps[0] + "/"
            plist_path = app_prefix + "Info.plist"
            try:
                plist_member = archive.getinfo(plist_path)
                if plist_member.file_size > MAX_PLIST_SIZE:
                    raise InventoryError("Info.plist exceeds safe limit")
                info = plistlib.loads(archive.read(plist_path))
            except (KeyError, ValueError, plistlib.InvalidFileException) as exc:
                raise InventoryError("missing or invalid Info.plist") from exc
            if not isinstance(info, dict):
                raise InventoryError("Info.plist must be a dictionary")
            global_extensions = Counter(
                PurePosixPath(item.filename).suffix.lower() or "(none)"
                for item in file_members
            )
            variants = {}
            asset_mirrors = {}
            for variant in VARIANTS:
                prefix = app_prefix + variant + "/"
                files = {item.filename[len(prefix):]: item
                         for item in file_members if item.filename.startswith(prefix)}
                variants[variant] = {
                    "file_count": len(files),
                    "by_extension": dict(sorted(Counter(
                        PurePosixPath(name).suffix.lower() or "(none)"
                        for name in files
                    ).items())),
                }
                asset_mirrors[variant] = files
            a, b = (asset_mirrors[k] for k in VARIANTS)
            common = set(a) & set(b)
            matching = sum(
                a[name].file_size == b[name].file_size
                and a[name].CRC == b[name].CRC
                for name in common
            )
            # Aggregate paired files by extension without recording paths or
            # original bytes. Exact relative paths (not mere basenames) are
            # required for a match; CRC32 is a fast comparison, not a hash
            # attestation of authentic game behavior.
            extensions_a = {}
            extensions_b = {}
            for name in a:
                ext = PurePosixPath(name).suffix.lower() or "(none)"
                extensions_a.setdefault(ext, set()).add(name)
            for name in b:
                ext = PurePosixPath(name).suffix.lower() or "(none)"
                extensions_b.setdefault(ext, set()).add(name)
            extension_parity = {}
            for ext in sorted(set(extensions_a) | set(extensions_b)):
                names_a = extensions_a.get(ext, set())
                names_b = extensions_b.get(ext, set())
                paired = names_a & names_b
                equal = sum(
                    a[name].file_size == b[name].file_size
                    and a[name].CRC == b[name].CRC
                    for name in paired
                )
                extension_parity[ext] = {
                    VARIANTS[0]: len(names_a),
                    VARIANTS[1]: len(names_b),
                    "paired": len(paired),
                    "matching_size_and_crc": equal,
                    "different_size_or_crc": len(paired) - equal,
                    "only_in_" + VARIANTS[0]: len(names_a - names_b),
                    "only_in_" + VARIANTS[1]: len(names_b - names_a),
                }
            return {
                "schema_version": 2,
                "application": {
                    "bundle_identifier": str(info.get("CFBundleIdentifier", "")),
                    "bundle_version": str(info.get("CFBundleVersion", "")),
                    "minimum_ios": str(info.get("MinimumOSVersion", "")),
                    "device_families": info.get("UIDeviceFamily", []),
                },
                "zip": {
                    "file_count": len(file_members),
                    "uncompressed_bytes": total,
                    "crc_verified": check_crc,
                },
                "extensions": dict(sorted(global_extensions.items())),
                "resource_counts": {ext: global_extensions.get(ext, 0)
                                    for ext in RESOURCE_TYPES},
                "variants": variants,
                "mirror_analysis": {
                    "common_relative_paths": len(common),
                    "matching_size_and_crc": matching,
                    "by_extension": extension_parity,
                    "variant_only_counts": {
                        VARIANTS[0]: len(set(a) - set(b)),
                        VARIANTS[1]: len(set(b) - set(a)),
                    },
                },
                "original_assets_embedded_in_report": False,
            }
    except (zipfile.BadZipFile, OSError) as exc:
        raise InventoryError("cannot inspect the IPA ZIP") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path, help="private local original IPA")
    parser.add_argument("--output", type=Path, help="private JSON output path")
    parser.add_argument("--verify-crc", action="store_true",
                        help="read and CRC-check every archived member")
    args = parser.parse_args()
    try:
        report = inspect_ipa(args.ipa, check_crc=args.verify_crc)
    except InventoryError as exc:
        parser.error(str(exc))
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
