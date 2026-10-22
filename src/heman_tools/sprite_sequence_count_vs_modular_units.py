"""Stage166: challenge candidate-count interpretations with lexical and 82-byte evidence.

Neither the unknown u32 after a SpriteSeqData record's marker nor an
82-byte serialized extension is a proven animation frame.  Evaluate,
without exposing source values, how often that u32 agrees with
(1) independently indexed length-prefixed cut-name references, and
(2) the number of extra 82-byte units in the observed source gaps.

The second comparison is only defined when *every* inter-name gap and
the terminal tail match Stage165's explicit candidate modular families.
Values, names, private per-record geometry, pixels and exact offsets
never appear in exported aggregate reports.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile
import struct

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, MAX_MEMBERS, _safe_read
from .sprite_repo_wad_index import (
    SCREENS, MAX_REPO_BYTES, MAX_WAD_BYTES, SpriteIndexFormatError,
    parse_sprite_repository, _text,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from .sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD
from .sprite_sequence_failure_strata import _PREFIX_GROUPS, _COUNT_GROUPS, _count_group
from .sprite_sequence_cut_anchor_scan import _packed_cut_names
from .sprite_sequence_modular_anchor_geometry import (
    _paired_name_geometry, _gap_class, _tail_class, _GAP_BASES,
    _GAP_LABELS, summarize_sequence_modular_anchor_geometry,
)

_HEAD = struct.Struct("<II")
_U32 = struct.Struct("<I")
_COMPARISON = ("less_than_unknown_count", "equal_unknown_count",
               "greater_than_unknown_count")


def _comparison(observed: int, declared: int) -> str:
    if type(observed) is not int or type(declared) is not int:
        raise ValueError("Invalid lexical-count comparison")
    if observed < 0 or declared < 1:
        raise ValueError("Invalid source count")
    return _COMPARISON[(observed > declared) - (observed < declared) + 1]


def _extra_82_units(gaps: tuple[int, ...], tail: int) -> int | None:
    """Return only a hypothetical count of 82-byte extensions.

    It is NOT the original number of rendered animation frames.
    """
    if type(gaps) is not tuple or type(tail) is not int or tail < 0:
        raise ValueError("Invalid bounded lexical geometry")
    if _tail_class(tail) != "tail_64_plus_82n":
        return None
    extra = (tail - 64) // 82
    for gap in gaps:
        label = _gap_class(gap)
        if label == "other_gap":
            return None
        idx = _GAP_LABELS.index(label)
        if idx >= len(_GAP_BASES):
            raise SpriteIndexFormatError("Bad modular gap category")
        extra += (gap - _GAP_BASES[idx]) // 82
    return extra


def summarize_sequence_count_vs_modular_units(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    parent = summarize_sequence_modular_anchor_geometry(
        sequence_repos, sequence_wads, cut_repos
    )
    rows = parse_sprite_repository(
        sequence_repos[SCREENS[0]],
        expected_label="SpriteSeqData", expected_wad=WAD_PATH,
    )
    cuts = parse_sprite_repository(
        cut_repos[SCREENS[0]],
        expected_label="SpriteCutData", expected_wad=CUT_WAD,
    )
    keys = frozenset(x.key for x in cuts)
    packed = _packed_cut_names(keys)
    pairs = [_intervals(rows, sequence_wads[s]) for s in SCREENS]
    counts = {
        word: {count: Counter() for count in _COUNT_GROUPS}
        for word in _PREFIX_GROUPS
    }
    for a, b in zip(*pairs):
        parsed = []
        for record in (a, b):
            _, pos = _text(record, 0)
            _, candidate_count = _HEAD.unpack_from(record, pos)
            if candidate_count == 0:
                parsed.append(None)
                continue
            firstword = _U32.unpack_from(record, pos+8)[0]
            geometry = _paired_name_geometry(record, pos, keys, packed)
            parsed.append((candidate_count, firstword, geometry))

        if parsed[0] is None and parsed[1] is None:
            continue
        if parsed[0] is None or parsed[1] is None:
            raise SpriteIndexFormatError("Paired source count differs")
        declared, firstword, first_geometry = parsed[0]
        declared_b, firstword_b, second_geometry = parsed[1]
        if declared != declared_b or firstword != firstword_b or (
                (first_geometry is None) != (second_geometry is None)):
            raise SpriteIndexFormatError("Paired source lexical header differs")
        if first_geometry is None:
            continue

        group = "first_u32_one" if firstword == 1 else "first_u32_other"
        c = counts[group][_count_group(declared)]
        gaps, tail = first_geometry
        c["known_first_cut_records"] += 1
        c["records_with_later_cut_names"] += bool(gaps)
        c["indexed_secondary_name_intervals"] += len(gaps)
        c["gap_geometry_identical_across_screen_packs"] += (
            first_geometry == second_geometry
        )
        c["references_" + _comparison(1+len(gaps), declared)] += 1
        c["unknown_count_one_with_more_than_one_indexed_reference"] += (
            declared == 1 and len(gaps) > 0
        )
        extra = _extra_82_units(gaps, tail)
        if extra is None:
            c["unclassifiable_under_82_geometry"] += 1
            continue
        c["complete_modular_geometry"] += 1
        c["extra82_" + _comparison(extra, declared)] += 1
        c["unknown_count_one_with_positive_82_extensions"] += (
            declared == 1 and extra > 0
        )
        c["unknown_count_multi_with_zero_82_extensions"] += (
            declared > 1 and extra == 0
        )

    parent_by = parent["by_firstword_and_declared_count"]
    out = {}
    for group in _PREFIX_GROUPS:
        out[group] = {}
        for count in _COUNT_GROUPS:
            c = counts[group][count]
            source = parent_by[group][count]
            for field in (
                "known_first_cut_records",
                "indexed_secondary_name_intervals",
                "gap_geometry_identical_across_screen_packs",
            ):
                source_key = (
                    "inter_name_gap_count" if field == "indexed_secondary_name_intervals"
                    else field
                )
                if c[field] != source[source_key]:
                    raise SpriteIndexFormatError("Stage165 lexical controls disagree")
            if c["records_with_later_cut_names"] != source[
                "records_with_secondary_indexed_names"
            ]:
                raise SpriteIndexFormatError("Stage165 later-cut totals disagree")
            if (sum(c["references_"+v] for v in _COMPARISON) !=
                    c["known_first_cut_records"]):
                raise SpriteIndexFormatError("Missing source name count controls")
            if (sum(c["extra82_"+v] for v in _COMPARISON) !=
                    c["complete_modular_geometry"]):
                raise SpriteIndexFormatError("Missing modular-unit controls")
            if (c["complete_modular_geometry"] +
                    c["unclassifiable_under_82_geometry"] !=
                    c["known_first_cut_records"]):
                raise SpriteIndexFormatError("Source modular controls incomplete")
            out[group][count] = {
                "known_first_cut_records": c["known_first_cut_records"],
                "registered_name_reference_count_vs_unknown_u32": {
                    value: c["references_"+value] for value in _COMPARISON
                },
                "complete_modular_geometry": c["complete_modular_geometry"],
                "unclassifiable_under_82_geometry":
                    c["unclassifiable_under_82_geometry"],
                "extra_82_byte_extensions_vs_unknown_u32": {
                    value: c["extra82_"+value] for value in _COMPARISON
                },
                "unknown_count_one_with_multiple_cut_references":
                    c["unknown_count_one_with_more_than_one_indexed_reference"],
                "unknown_count_one_with_positive_extra_82_units":
                    c["unknown_count_one_with_positive_82_extensions"],
                "unknown_count_multi_with_zero_extra_82_units":
                    c["unknown_count_multi_with_zero_82_extensions"],
            }
    return {
        "classification": "owner_private_sprite_unknown_count_vs_82_unit_falsification",
        "by_firstword_and_declared_count": out,
        "independent_stage165_lexical_and_gap_controls_reconciled": True,
        "all_name_references_are_proven_animation_frames": False,
        "unknown_u32_is_proven_animation_frame_count": False,
        "modular_82_extensions_are_proven_rendered_frames": False,
        "frame_durations_transitions_hitboxes_or_runtime_verified": False,
        "original_sprite_import_to_switch_permitted": False,
        "original_names_header_values_offsets_and_gap_arrays_exported": False,
    }


def audit_private_sequence_count_vs_modular_units(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as z:
        infos = z.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP members")
        lookup = {item.filename: item for item in infos}
        if len(lookup) != len(infos):
            raise ValueError("Duplicate original ZIP member")
        repos, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            prefix = PREFIX + screen + "/"
            repos[screen] = _safe_read(
                z, lookup.get(prefix + REPO_PATH), MAX_REPO_BYTES
            )
            wads[screen] = _safe_read(
                z, lookup.get(prefix + WAD_PATH), MAX_WAD_BYTES
            )
            cuts[screen] = _safe_read(
                z, lookup.get(prefix + CUT_REPO), MAX_REPO_BYTES
            )
    return summarize_sequence_count_vs_modular_units(repos, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    summary = audit_private_sequence_count_vs_modular_units(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("Private source count vs 82-unit comparison written locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
