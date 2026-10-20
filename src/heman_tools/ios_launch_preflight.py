"""Offline, metadata-only launch/capture prerequisites for a privately owned IPA.

Do not extract, upload, resign, execute or patch the original application.
A readable armv7 Mach-O header does not prove installation or runtime success.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import plistlib
import re
import stat
import struct
import zipfile

from .frame_alignment import _private_path

MAX_MEMBERS = 100_000
MAX_PLIST_BYTES = 2 * 1024 * 1024
MAX_EXECUTABLE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_ZIP_BYTES = 3 * 1024 * 1024 * 1024
MAX_COMMANDS = 512
MAX_LOAD_COMMAND_BYTES = 2 * 1024 * 1024

MH_MAGIC_LE_32 = b"\xce\xfa\xed\xfe"
MH_MAGIC_BE_32 = b"\xfe\xed\xfa\xce"
MH_MAGIC_LE_64 = b"\xcf\xfa\xed\xfe"
FAT_MAGIC = (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
             b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")
LC_VERSION_MIN_IPHONEOS = 0x25
LC_ENCRYPTION_INFO = 0x21
LC_CODE_SIGNATURE = 0x1D
CPU_TYPE_ARM = 12
MH_EXECUTE = 2


def _version(number: int) -> str:
    return f"{(number >> 16) & 0xFFFF}.{(number >> 8) & 255}.{number & 255}"


def inspect_macho_header(data: bytes) -> dict:
    """Parse only a bounded 32-bit *thin* Mach-O header and load commands."""
    if not isinstance(data, bytes) or len(data) < 28:
        raise ValueError("invalid or incomplete Mach-O header")
    magic = data[:4]
    if magic in FAT_MAGIC:
        raise ValueError("fat Mach-O needs a separate, verified slice parser")
    if magic == MH_MAGIC_LE_64 or magic == b"\xfe\xed\xfa\xcf":
        raise ValueError("64-bit Mach-O is outside this 32-bit audit")
    if magic == MH_MAGIC_LE_32:
        byteorder = "<"
    elif magic == MH_MAGIC_BE_32:
        byteorder = ">"
    else:
        raise ValueError("unrecognized Mach-O magic")
    if len(data) > MAX_EXECUTABLE_BYTES:
        raise ValueError("executable exceeds private inspection bound")
    _, cpu, subtype, filetype, ncmds, sizeofcmds, _ = struct.unpack_from(
        byteorder + "IiiIIII", data, 0)
    if (not 1 <= ncmds <= MAX_COMMANDS
            or not 8 * ncmds <= sizeofcmds <= MAX_LOAD_COMMAND_BYTES
            or sizeofcmds > len(data) - 28):
        raise ValueError("invalid or out-of-bounds Mach-O load commands")
    offset = 28
    end = 28 + sizeofcmds
    minimum = sdk = cryptid = None
    code_signature_present = False
    for _ in range(ncmds):
        if offset + 8 > end:
            raise ValueError("truncated load command header")
        cmd, cmdsize = struct.unpack_from(byteorder + "II", data, offset)
        if cmdsize < 8 or cmdsize % 4 or cmdsize > end - offset:
            raise ValueError("invalid Mach-O load command size")
        if cmd == LC_VERSION_MIN_IPHONEOS:
            if cmdsize < 16 or minimum is not None:
                raise ValueError("malformed or repeated iOS version command")
            minimum, sdk = struct.unpack_from(byteorder + "II", data, offset + 8)
        elif cmd == LC_ENCRYPTION_INFO:
            if cmdsize < 20 or cryptid is not None:
                raise ValueError("malformed or repeated encryption command")
            cryptoff, cryptsize, cryptid = struct.unpack_from(
                byteorder + "III", data, offset + 8)
            if cryptoff > len(data) or cryptsize > len(data) - cryptoff:
                raise ValueError("out-of-bounds encrypted payload region")
        elif cmd == LC_CODE_SIGNATURE:
            if cmdsize < 16 or code_signature_present:
                raise ValueError("malformed or repeated code-signature command")
            signature_off, signature_size = struct.unpack_from(
                byteorder + "II", data, offset + 8)
            if (signature_off > len(data)
                    or signature_size > len(data) - signature_off):
                raise ValueError("out-of-bounds code-signature region")
            code_signature_present = True
        offset += cmdsize
    if offset != end:
        raise ValueError("Mach-O load commands do not exactly fill header")
    cpu_name = "arm" if cpu == CPU_TYPE_ARM else "other"
    subtype_base = subtype & 0x00FFFFFF
    arch = "armv7" if cpu == CPU_TYPE_ARM and subtype_base == 9 else (
        "arm32-other" if cpu == CPU_TYPE_ARM else "unsupported")
    return {
        "thin_32_bit_macho": True,
        "cpu_type": cpu_name,
        "architecture": arch,
        "executable_filetype": filetype == MH_EXECUTE,
        "minimum_ios_from_macho": _version(minimum) if minimum is not None else None,
        "sdk_from_macho": _version(sdk) if sdk is not None else None,
        "encryption_cryptid": cryptid,
        "code_signature_command_present": code_signature_present,
        "code_signature_validity_verified": False,
        "load_commands_structurally_valid": True,
    }


def _member(archive: zipfile.ZipFile, names: dict, path: str,
            maximum: int) -> bytes:
    item = names.get(path)
    if item is None or item.is_dir() or item.flag_bits & 1:
        raise ValueError("missing, encrypted or invalid selected IPA member")
    if not 1 <= item.file_size <= maximum:
        raise ValueError("selected IPA member exceeds inspection limits")
    if stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK:
        raise ValueError("selected IPA member is a symbolic link")
    return archive.read(item)


def _string(value: object, label: str, maximum=128) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= maximum
            or not value.isprintable()
            or any(ord(ch) < 32 for ch in value)):
        raise ValueError(f"invalid {label}")
    return value


def inspect_private_ipa_launch(ipa: Path) -> dict:
    """Report source-file compatibility *requirements*, never execution."""
    if not ipa.is_file() or not zipfile.is_zipfile(ipa):
        raise ValueError("expected a readable local IPA archive")
    with zipfile.ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("excessive IPA member count")
        names = {}
        total_size = 0
        for item in infos:
            name = item.filename
            if (not name or name.startswith("/") or "\\" in name
                    or "\x00" in name
                    or any(part in (".", "..") for part in name.split("/"))
                    or name in names
                    or stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK
                    or item.flag_bits & 1):
                raise ValueError("unsafe, encrypted or duplicated ZIP entry")
            names[name] = item
            total_size += item.file_size
            if total_size > MAX_TOTAL_ZIP_BYTES:
                raise ValueError("IPA uncompressed size exceeds safe limit")
        appdirs = {
            parts[1] for name in names
            if name.startswith("Payload/")
            for parts in [name.split("/")]
            if len(parts) >= 3 and parts[1].endswith(".app")
        }
        if len(appdirs) != 1:
            raise ValueError("expected exactly one .app bundle")
        prefix = "Payload/" + next(iter(appdirs)) + "/"
        try:
            info = plistlib.loads(_member(
                archive, names, prefix + "Info.plist", MAX_PLIST_BYTES))
        except (plistlib.InvalidFileException, TypeError, ValueError) as exc:
            raise ValueError("malformed application Info.plist") from exc
        if not isinstance(info, dict):
            raise ValueError("Info.plist must be a dictionary")
        executable = _string(info.get("CFBundleExecutable"), "executable name")
        if (executable.startswith(".")
                or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*",
                                    executable)):
            raise ValueError("unsafe executable filename")
        binary = _member(
            archive, names, prefix + executable, MAX_EXECUTABLE_BYTES)
    metadata = inspect_macho_header(binary)
    minimum = _string(info.get("MinimumOSVersion"), "minimum iOS")
    bundle = _string(info.get("CFBundleIdentifier"), "bundle identifier", 255)
    version = _string(info.get("CFBundleVersion"), "bundle version")
    devices = info.get("UIDeviceFamily", [])
    capabilities = info.get("UIRequiredDeviceCapabilities", [])
    orientations = info.get("UISupportedInterfaceOrientations", [])
    if (not isinstance(devices, list) or len(devices) > 10
            or any(type(v) is not int for v in devices)):
        raise ValueError("malformed device family metadata")
    if (not isinstance(capabilities, list) or len(capabilities) > 32
            or any(not isinstance(v, str) or not v.isprintable()
                   for v in capabilities)):
        raise ValueError("malformed capability metadata")
    if (not isinstance(orientations, list) or len(orientations) > 20
            or any(not isinstance(v, str) or not v.isprintable()
                   for v in orientations)):
        raise ValueError("malformed orientation metadata")

    declared_min = metadata["minimum_ios_from_macho"]
    consistent_min = False
    # Accept "4.3" and "4.3.0" as semantically equal.
    try:
        os_parts = tuple(int(p) for p in minimum.split("."))
        macho_parts = tuple(int(p) for p in declared_min.split(".")) \
            if declared_min is not None else ()
        consistent_min = (1 <= len(os_parts) <= 3
                          and all(0 <= number <= 65535 for number in os_parts)
                          and os_parts + (0,) * (3 - len(os_parts))
                          == macho_parts + (0,) * (3 - len(macho_parts)))
    except (ValueError, AttributeError):
        consistent_min = False

    launch_metadata = {
        "bundle_identifier": bundle,
        "bundle_version": version,
        "minimum_ios_from_info_plist": minimum,
        "iphone_ipad_families": sorted(set(devices)),
        "required_device_capabilities": sorted(set(capabilities)),
        "declared_orientations": sorted(set(orientations)),
    }
    blockers = []
    if metadata["architecture"] != "armv7":
        blockers.append("executable_architecture_not_armv7")
    if not metadata["executable_filetype"]:
        blockers.append("macho_filetype_not_executable")
    if not consistent_min:
        blockers.append("plist_macho_minimum_version_unreconciled")
    if metadata["encryption_cryptid"] is None:
        blockers.append("encryption_header_status_unknown")
    elif metadata["encryption_cryptid"] != 0:
        blockers.append("binary_reports_encrypted_executable")
    return {
        "schema_version": 1,
        "ipa_metadata": launch_metadata,
        "macho_metadata": metadata,
        "metadata_consistency_blockers": blockers,
        "compatibility_hypotheses": {
            "requires_legacy_32_bit_arm_execution_support": (
                metadata["cpu_type"] == "arm"),
            "opengles2_required_by_plist": "opengles-2" in capabilities,
            "requires_launch_and_input_mapping_test": True,
            "claimed_runtime_frame_rate": None,
        },
        "real_ios_app_started": False,
        "ios_gameplay_frames_recorded": False,
        "ios_touch_input_mapping_verified": False,
        "original_ios_frame_rate_measured": False,
        "code_signature_validity_verified": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
        "original_game_assets_exported": False,
        "interpretation": (
            "Private IPA header and manifest consistency only. It does not "
            "prove installability, valid signing, lawful compatibility, "
            "iOS runtime behavior, capture readiness or actual physics."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    output = _private_path(args.out)
    report = inspect_private_ipa_launch(args.ipa)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                 sort_keys=True) + "\n", encoding="utf-8")
    print("IPA metadata checked; real iOS gameplay remains unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
