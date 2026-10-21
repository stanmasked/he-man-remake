"""Cross-resource lexicon constraints on *hypothetical* original physics tails.

These are intentionally restricted SOURCE-PRIVATE aggregate-only tests:
candidate trailer [u16 UTF-16 token][0..96 uninterpreted bytes] for each
declared group, exact EOF and matching a separately parsed vocabulary.

Lexical matches never establish record boundaries, field ownership,
collision response, object-shape links, or original-game behavior.
The privately held IPA and resource-specific strings must never enter CI.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_records import _read_text, parse_physics_structure, PhysicsRecordFormatError
from .physics_opaque_probe import _capture_opaque
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, MAX_SHAPES, MAX_ITEM_BYTES,
    PHYSICS_DIR, SHAPE_DIR, _paired,
)
from .physics_tail_candidates import MAX_FIXED_BYTES_PER_GROUP
from .shapes import parse_shape

MAX_LEXICAL_TAIL_BYTES = 1024
MAX_LEXICAL_GROUPS = 64
AMBIGUOUS = 2


def lexically_constrained_paths(
    trailer: bytes,
    groups: int,
    allowed_tokens: frozenset[str],
    *,
    max_padding: int = MAX_FIXED_BYTES_PER_GROUP,
) -> int:
    """Return 0, 1 or 2 (>=2) suffix-layout parses matching allowed tokens.

    The candidate is ONLY:
        [u16-length UTF16LE token from allowed_tokens][N unknown bytes]
    repeated groups times; N may vary per group from 0..max_padding.

    No candidate path, widths or parsed original token leaves this call.
    Saturating at 2 prevents arbitrary ambiguity being called unique.
    """
    if (type(trailer) is not bytes or not 1 <= len(trailer) <= MAX_LEXICAL_TAIL_BYTES
            or type(groups) is not int or not 1 <= groups <= MAX_LEXICAL_GROUPS
            or not isinstance(allowed_tokens, frozenset)
            or any(not isinstance(x, str) for x in allowed_tokens)
            or type(max_padding) is not int
            or not 0 <= max_padding <= MAX_FIXED_BYTES_PER_GROUP):
        raise ValueError("Invalid bounded cross-resource candidate input")
    if not allowed_tokens:
        return 0

    @lru_cache(maxsize=None)
    def token_end(at: int) -> int:
        if at < 0 or at + 2 > len(trailer):
            return -1
        try:
            token, end = _read_text(trailer, at, allow_empty=True)
        except PhysicsRecordFormatError:
            return -1
        return end if token in allowed_tokens else -1

    @lru_cache(maxsize=None)
    def count_paths(index: int, at: int) -> int:
        if index == groups:
            return int(at == len(trailer))
        end = token_end(at)
        if end < 0:
            return 0
        rest = groups-index-1
        ways = 0
        for padding in range(max_padding+1):
            new_pos = end+padding
            if new_pos+2*rest > len(trailer):
                break
            ways += count_paths(index+1,new_pos)
            if ways >= AMBIGUOUS:
                return AMBIGUOUS
        return ways

    return count_paths(0, 0)


def summarize_lexicon_restrictions(
    physics: dict[str, bytes],
    shapes: dict[str, bytes],
) -> dict:
    """Fully source-private evidence in, aggregate nonidentifying counters out."""
    if (not isinstance(physics, dict) or not isinstance(shapes, dict)
            or not 1 <= len(physics) <= MAX_PHYSICS
            or not 1 <= len(shapes) <= MAX_SHAPES):
        raise ValueError("Missing or excessive source resource group")
    labels: set[str] = set()
    references: set[str] = set()
    tails: list[tuple[int, bytes]] = []
    for name, blob in physics.items():
        if (not isinstance(name, str)
                or not name.endswith((".ps2d", ".pstruct2d"))
                or "/" in name or "\\" in name
                or type(blob) is not bytes or len(blob) > MAX_ITEM_BYTES):
            raise ValueError("Invalid private physics resource")
        decoded = parse_physics_structure(blob)
        labels.update(rec.label for rec in decoded.records)
        references.update(s for rec in decoded.records for s in rec.shape_reference_strings)
        _unused_blocks, count, tail = _capture_opaque(blob)
        if count:
            if len(tail) > MAX_LEXICAL_TAIL_BYTES or count > MAX_LEXICAL_GROUPS:
                raise ValueError("Source trailer exceeds bounded lexical study")
            tails.append((count, tail))

    stems: set[str] = set()
    for name, blob in shapes.items():
        if (not isinstance(name, str) or not name.endswith(".shape")
                or len(name) <= 6 or "/" in name or "\\" in name
                or type(blob) is not bytes or len(blob) > MAX_ITEM_BYTES):
            raise ValueError("Invalid private shape member")
        parse_shape(blob)
        stems.add(name[:-6])

    vocabularies = {
        "main_record_labels_including_empty": frozenset(labels),
        "nonempty_main_record_labels": frozenset(x for x in labels if x),
        "main_record_shape_reference_strings": frozenset(references),
        "validated_shape_file_stems": frozenset(stems),
    }
    tally: dict[str, int] = {}
    for key, allowed in vocabularies.items():
        zero = one = many = zero_multi = one_multi = many_multi = 0
        for groups, tail in tails:
            paths = lexically_constrained_paths(tail, groups, allowed)
            zero += paths == 0
            one += paths == 1
            many += paths == 2
            if groups > 1:
                zero_multi += paths == 0
                one_multi += paths == 1
                many_multi += paths == 2
        tally[key + "_no_complete_parses"] = zero
        tally[key + "_one_complete_parse"] = one
        tally[key + "_multiple_complete_parses"] = many
        tally[key + "_multi_group_no_complete_parses"] = zero_multi
        tally[key + "_multi_group_one_complete_parse"] = one_multi
        tally[key + "_multi_group_multiple_complete_parses"] = many_multi
        if zero+one+many != len(tails):
            raise ValueError("Incomplete private trailer candidate accounting")

    return {
        "classification": "private_original_physics_tail_cross_resource_lexicon_falsification",
        "source_physics_file_count": len(physics),
        "source_shape_file_count": len(shapes),
        "nonempty_trailer_file_count": len(tails),
        "multi_group_trailer_file_count": sum(count > 1 for count, _ in tails),
        "distinct_nonempty_main_record_labels": len(labels-{""}),
        "declared_lexicon_candidate_max_opaque_bytes": MAX_FIXED_BYTES_PER_GROUP,
        **tally,
        "lexical_shape_references_prove_runtime_links": False,
        "a_unique_candidate_proves_record_boundaries": False,
        "unknown_trailer_item_fields_decoded": False,
        "original_collision_geometry_or_physics_verified": False,
        "allow_switch_original_geometry_import": False,
        "source_names_bytes_offsets_paths_and_hashes_in_output": False,
    }


def audit_private_tail_lexicons(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Original private source archive missing")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Oversized private source index")
        indexed = {item.filename: item for item in infos}
        if len(indexed) != len(infos):
            raise ValueError("Duplicate private archive member")
        sources = _paired(archive,indexed,PHYSICS_DIR,(".ps2d",".pstruct2d"),
                          max_items=MAX_PHYSICS)
        shapes = _paired(archive,indexed,SHAPE_DIR,(".shape",),
                         max_items=MAX_SHAPES)
        return summarize_lexicon_restrictions(sources,shapes)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    options=parser.parse_args(argv)
    out=private_output_path(options.out)
    result=audit_private_tail_lexicons(options.ipa)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Private cross-resource trailer lexicon aggregate recorded under local_reports.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
