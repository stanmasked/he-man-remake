"""Private-only .ps2d/.pstruct2d -> .shape lexical evidence census.

Searches for exact [u16 UTF-16 code-unit length][UTF-16LE shape stem]
byte sequences. Those matches are candidates, not proof of parser field
meaning, runtime binding, collision ownership or game physics.

No original asset names, payloads, hashes, positions or vertex data leave
this process. CI uses deliberately fabricated ZIPs exclusively.
"""
from __future__ import annotations

import argparse
import json
import stat
import struct
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .shapes import parse_shape

PREFIX = "Payload/MOTU.app/"
SCREENS = ("screen-med", "screen-xlarge")
SHAPE_DIR = "geometry/"
PHYSICS_DIR = "physics_struct/"
REGISTRY = "meta/GeometryData.repo"
MAX_MEMBERS = 100_000
MAX_SHAPES = 2048
MAX_PHYSICS = 1024
MAX_ITEM_BYTES = 1_000_000
MAX_REGISTRY_BYTES = 8_000_000
MAX_SELECTED_BYTES = 64_000_000


def _member_name(name: str, *, directory: str, suffixes: tuple[str, ...]) -> str | None:
    if not name.startswith(directory):
        return None
    tail = name[len(directory):]
    # The actual original geometry directory also has non-.shape members.
    # Ignore those without mistaking them for malformed selected .shape files.
    if not tail.endswith(suffixes):
        return None
    if (not tail or "/" in tail or "\\" in tail or "\x00" in tail
            or len(tail) > 255):
        raise ValueError("Malformed or nested selected private resource")
    return tail


def _safe_read(archive: ZipFile, info, max_size=MAX_ITEM_BYTES) -> bytes:
    if (info is None or info.is_dir() or info.flag_bits & 1
            or not 1 <= info.file_size <= max_size
            or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
        raise ValueError("Missing or unsafe selected private ZIP member")
    raw = archive.read(info)
    if len(raw) != info.file_size:
        raise ValueError("Incomplete selected ZIP resource")
    return raw


def _paired(archive: ZipFile, index: dict, directory: str, suffixes: tuple[str, ...],
            *, max_items: int) -> dict[str, bytes]:
    names_by_pack = []
    for screen in SCREENS:
        prefix = PREFIX + screen + "/" + directory
        names = {}
        for member_name, info in index.items():
            if not member_name.startswith(prefix):
                continue
            name = _member_name(member_name[len(PREFIX + screen + "/"):],
                                directory=directory, suffixes=suffixes)
            if name is not None:
                names[name] = info
        if len(names) > max_items or not names:
            raise ValueError("Missing or excessive private resource group")
        names_by_pack.append(names)
    if names_by_pack[0].keys() != names_by_pack[1].keys():
        raise ValueError("Source resolution packs have different resources")
    selected = {}
    total = 0
    for name in sorted(names_by_pack[0]):
        source = _safe_read(archive, names_by_pack[0][name])
        other = _safe_read(archive, names_by_pack[1][name])
        total += len(source) + len(other)
        if total > MAX_SELECTED_BYTES:
            raise ValueError("Source private resource group exceeds size budget")
        if source != other:
            raise ValueError("Source resolution pack bytes differ")
        selected[name] = source
    return selected


def _stem_pattern(stem: str) -> bytes:
    encoded = stem.encode("utf-16le")
    units = len(encoded) // 2
    if not 1 <= units <= 512:
        raise ValueError("Unusable shape identifier length")
    return struct.pack("<H", units) + encoded


def summarize_shape_lexemes(shapes: dict[str, bytes], physics: dict[str, bytes],
                            registry: bytes) -> dict:
    """Aggregate byte-pattern evidence, not a fully parsed physics graph."""
    if not shapes or not physics or not registry:
        raise ValueError("Missing required private candidate source")
    if len(shapes) > MAX_SHAPES or len(physics) > MAX_PHYSICS:
        raise ValueError("Excessive candidate data")
    stems = {}
    for name, data in shapes.items():
        if (not isinstance(name, str) or not name.endswith(".shape")
                or len(name) <= 6 or "/" in name or "\\" in name):
            raise ValueError("Invalid shape identifier")
        if not isinstance(data, bytes) or len(data) > MAX_ITEM_BYTES:
            raise ValueError("Invalid shape bytes")
        parse_shape(data)  # Existing strict decoder, no geometry exported.
        stems[name[:-6]] = _stem_pattern(name[:-6])
    if len(stems) != len(shapes):
        raise ValueError("Duplicate shape stem")
    matched_files = 0
    candidate_edges = 0
    referenced = set()
    for name, data in physics.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d")) or
                "/" in name or "\\" in name or
                not isinstance(data, bytes) or len(data) > MAX_ITEM_BYTES):
            raise ValueError("Invalid physics resource candidate")
        hits = [stem for stem, pattern in stems.items() if pattern in data]
        candidate_edges += len(hits)
        matched_files += bool(hits)
        referenced.update(hits)
    if not isinstance(registry, bytes) or len(registry) > MAX_REGISTRY_BYTES:
        raise ValueError("Invalid registry payload")
    registered = {stem for stem, pattern in stems.items() if pattern in registry}
    return {
        "classification": "owner_private_physics_to_shape_lexical_reference_census",
        "paired_original_shape_count": len(shapes),
        "paired_physics_struct_resource_count": len(physics),
        "physics_files_with_shape_identifier_lexeme": matched_files,
        "physics_file_shape_identifier_candidate_pairs": candidate_edges,
        "unique_shapes_lexically_referenced_in_physics_files": len(referenced),
        "shapes_with_matching_geometry_registry_lexeme": len(registered),
        "physics_shape_lexemes_missing_in_geometry_registry": len(referenced - registered),
        "source_resolution_packs_byte_identical": True,
        "length_prefixed_utf16_candidate_evidence_only": True,
        "physics_record_fields_decoded": False,
        "original_physics_resource_binding_verified": False,
        "source_level_object_shape_ownership_verified": False,
        "collision_hitbox_semantics_verified": False,
        "safe_for_switch_collision_import": False,
        "raw_source_names_bytes_vertices_and_hashes_in_report": False,
    }


def audit_private_physics_shape_census(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner private IPA not found")
    with ZipFile(ipa, "r") as archive:
        all_entries = archive.infolist()
        if len(all_entries) > MAX_MEMBERS:
            raise ValueError("Oversized private ZIP index")
        index = {item.filename: item for item in all_entries}
        if len(index) != len(all_entries):
            raise ValueError("Duplicate private ZIP member")
        shapes = _paired(archive, index, SHAPE_DIR, (".shape",),
                         max_items=MAX_SHAPES)
        physics = _paired(archive, index, PHYSICS_DIR,
                          (".ps2d", ".pstruct2d"), max_items=MAX_PHYSICS)
        registries = [_safe_read(
            archive, index.get(PREFIX + screen + "/" + REGISTRY),
            MAX_REGISTRY_BYTES
        ) for screen in SCREENS]
        if registries[0] != registries[1]:
            raise ValueError("Source registry differs across packs")
        return summarize_shape_lexemes(shapes, physics, registries[0])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    path = private_output_path(args.out)
    result = audit_private_physics_shape_census(args.ipa)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print("Private aggregate physics-to-shape candidate counts recorded under local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
