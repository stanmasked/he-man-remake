"""Bounded, offline inventory of a private ARMv7 iOS binary's linked dylibs.

A dependency list is not an API compatibility verdict. This tool does not
launch, decrypt, emulate or export executable bytes or source-game assets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import plistlib
import struct
import zipfile

from .frame_alignment import _private_path
from .ios_launch_preflight import (
    _member, _string, inspect_macho_header, inspect_private_ipa_launch,
    MAX_EXECUTABLE_BYTES, MAX_PLIST_BYTES,
)

LOAD_KINDS = {
    0x0000000C: "required",
    0x80000018: "weak",
    0x8000001F: "reexport",
    0x00000020: "lazy",
    0x80000023: "upward",
}
MAX_LINKED_LIBS = 128


def _dylib_class(name: str) -> str:
    if (name.startswith("/System/Library/Frameworks/")
            and ".framework/" in name):
        return "system_framework"
    if name.startswith("/usr/lib/"):
        return "system_library"
    if name.startswith("@"):
        return "runtime_relative"
    return "other"


def inspect_linked_dylibs(binary: bytes) -> dict:
    """Parse exact 32-bit Mach-O load commands; count without storing paths."""
    header = inspect_macho_header(binary)
    if binary[:4] == b"\xce\xfa\xed\xfe":
        order = "<"
    elif binary[:4] == b"\xfe\xed\xfa\xce":
        order = ">"
    else:
        raise ValueError("unsupported Mach-O byte order")
    _, _, _, _, ncmds, commands_size, _ = struct.unpack_from(
        order + "IiiIIII", binary, 0)
    pos, limit = 28, 28 + commands_size
    by_kind = Counter()
    by_class = Counter()
    duplicate_names = set()
    imports = []
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from(order + "II", binary, pos)
        if cmd in LOAD_KINDS:
            if cmdsize < 24:
                raise ValueError("truncated linked-library command")
            offset = struct.unpack_from(order + "I", binary, pos + 8)[0]
            if offset < 24 or offset >= cmdsize:
                raise ValueError("invalid Mach-O library-name offset")
            raw = binary[pos + offset:pos + cmdsize]
            nul = raw.find(b"\x00")
            if nul <= 0:
                raise ValueError("library path must be NUL terminated")
            try:
                name = raw[:nul].decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise ValueError("malformed UTF-8 linked-library name") from exc
            if (len(name) > 1024 or not name.isprintable()
                    or "\\" in name or any(ord(x) < 32 for x in name)):
                raise ValueError("invalid linked-library name")
            if name in duplicate_names:
                raise ValueError("duplicated linked-library import")
            duplicate_names.add(name)
            imports.append(name)
            if len(imports) > MAX_LINKED_LIBS:
                raise ValueError("excessive number of linked libraries")
            by_kind[LOAD_KINDS[cmd]] += 1
            by_class[_dylib_class(name)] += 1
        pos += cmdsize
    if pos != limit:
        raise ValueError("Mach-O command positions do not reconcile")
    return {
        "architecture": header["architecture"],
        "minimum_ios_from_macho": header["minimum_ios_from_macho"],
        "sdk_from_macho": header["sdk_from_macho"],
        "linked_library_count": len(imports),
        "by_load_kind": {kind: by_kind[kind]
                         for kind in LOAD_KINDS.values()},
        "by_path_category": {category: by_class[category] for category in (
            "system_framework", "system_library", "runtime_relative", "other")},
        "opengles_linked": any(
            "/OpenGLES.framework/OpenGLES" in name for name in imports),
        "openaudio_linked": any(
            "/OpenAL.framework/OpenAL" in name for name in imports),
        "uikit_linked": any("/UIKit.framework/UIKit" in name
                            for name in imports),
        "dependency_paths_embedded_in_report": False,
        "runtime_import_resolution_verified": False,
        "linked_symbols_or_runtime_api_coverage_verified": False,
        "source_ios_game_launched": False,
        "original_ios_gameplay_frames_recorded": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
    }


def inspect_ipa_dependencies(ipa: Path) -> dict:
    """Read a privately held IPA and extract only aggregate import counts."""
    baseline = inspect_private_ipa_launch(ipa)
    with zipfile.ZipFile(ipa) as archive:
        infos = archive.infolist()
        items = {info.filename: info for info in infos}
        # Full archive safety is checked in inspect_private_ipa_launch above.
        apps = sorted({name.split("/")[1] for name in items
                       if name.startswith("Payload/")
                       and len(name.split("/")) > 2
                       and name.split("/")[1].endswith(".app")})
        if len(apps) != 1:
            raise ValueError("expected one app bundle")
        prefix = "Payload/" + apps[0] + "/"
        info = plistlib.loads(
            _member(archive, items, prefix + "Info.plist", MAX_PLIST_BYTES))
        executable = _string(info.get("CFBundleExecutable"),
                             "executable name")
        if (executable.startswith(".") or "/" in executable
                or "\\" in executable):
            raise ValueError("unsafe executable name")
        binary = _member(
            archive, items, prefix + executable, MAX_EXECUTABLE_BYTES)
        report = inspect_linked_dylibs(binary)
    if (baseline["macho_metadata"]["architecture"] != report["architecture"]
            or baseline["macho_metadata"]["sdk_from_macho"] !=
                report["sdk_from_macho"]):
        raise ValueError("private IPA metadata changed during inspection")
    report.update({
        "schema_version": 1,
        "minimum_ios_from_plist": baseline["ipa_metadata"][
            "minimum_ios_from_info_plist"],
        "opengles2_required_by_plist": baseline["compatibility_hypotheses"][
            "opengles2_required_by_plist"],
        "static_dependency_inventory_complete": True,
        "touchhle_compatibility_established": False,
        "hardware_capture_success_verified": False,
    })
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ipa", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    target = _private_path(args.out)
    report = inspect_ipa_dependencies(args.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Private Mach-O dependency inventory saved. App launch NOT verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
