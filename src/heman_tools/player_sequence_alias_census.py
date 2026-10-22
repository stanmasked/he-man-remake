"""Stage187: aggregate-only audit of state-like aliases and directional sequence pairs.

The owner-private GO data is inspected locally. This module deliberately emits
only counts: no alias labels, sequence keys, byte offsets, or source bytes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, SCREENS, MAX_MEMBERS, _safe_read
from .sprite_repo_wad_index import MAX_REPO_BYTES, parse_sprite_repository

MAX_GO_BYTES = 8_000_000
MAX_REGION_BYTES = 1_000_000
MAX_SEQUENCE_KEYS = 5_000
MAX_TOKEN_UNITS = 64
_ALIAS = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,31}\Z")
_IGNORED_TOKENS = {
    "CDirectionalSprite", "game_player", "game_renderer2D",
    "normal", "battleArmor", "Cb2Body", "physics2D", "standingBody",
}
_U16 = struct.Struct("<H")


class SequenceAliasCensusError(ValueError):
    """Invalid or ambiguous input to the private sequence-alias census."""


def _length_prefixed_ascii_tokens(raw: bytes, start: int, end: int) -> tuple[tuple[int, str], ...]:
    """Scan a bounded region for length-prefixed printable UTF-16LE fields."""
    result = set()
    for at in range(start, end - 2):
        units = _U16.unpack_from(raw, at)[0]
        if not 3 <= units <= MAX_TOKEN_UNITS or at + 2 + 2 * units > end:
            continue
        encoded = raw[at + 2:at + 2 + 2 * units]
        if any(encoded[i + 1] != 0 or not 0x20 <= encoded[i] <= 0x7E
               for i in range(0, len(encoded), 2)):
            continue
        result.add((at, encoded[::2].decode("ascii")))
    return tuple(sorted(result))


def _find_sequence_references(
    raw: bytes, sequence_keys: frozenset[str], start: int, end: int,
) -> tuple[tuple[int, str], ...]:
    """Find exact length-prefixed repository keys, preserving repeated references."""
    result = []
    for key in sequence_keys:
        encoded = key.encode("utf-16le")
        cursor = start + 2
        while True:
            pos = raw.find(encoded, cursor, end)
            if pos < 0:
                break
            prefix = pos - 2
            if (prefix >= start and pos + len(encoded) <= end
                    and _U16.unpack_from(raw, prefix)[0] == len(key)):
                result.append((prefix, key))
            cursor = pos + 1
    return tuple(sorted(set(result)))


def _summarize_region(
    raw: bytes, sequence_keys: frozenset[str], start: int, end: int,
) -> tuple[dict, dict[str, list[tuple[str, str]]]]:
    refs = _find_sequence_references(raw, sequence_keys, start, end)
    tokens = _length_prefixed_ascii_tokens(raw, start, end)
    resource_like_unmatched = {
        value for _, value in tokens
        if "." in value and value.endswith((".e", ".w")) and value not in sequence_keys
    }
    aliases = [
        (pos, value) for pos, value in tokens
        if value not in sequence_keys and value not in _IGNORED_TOKENS
        and _ALIAS.fullmatch(value)
    ]

    pair_entries: list[tuple[str, tuple[str, str]]] = []
    ambiguous_groups = 0
    ambiguous_refs = 0
    assigned_ref_positions: set[int] = set()
    for index, (pos, alias) in enumerate(aliases):
        next_pos = aliases[index + 1][0] if index + 1 < len(aliases) else end
        group_refs = [(ref_pos, key) for ref_pos, key in refs if pos < ref_pos < next_pos]
        if not group_refs:
            continue
        assigned_ref_positions.update(ref_pos for ref_pos, _ in group_refs)
        suffixes = {key[-2:] for _, key in group_refs}
        if len(group_refs) == 2 and suffixes == {".e", ".w"}:
            east = next(key for _, key in group_refs if key.endswith(".e"))
            west = next(key for _, key in group_refs if key.endswith(".w"))
            pair_entries.append((alias, (east, west)))
        else:
            ambiguous_groups += 1
            ambiguous_refs += len(group_refs)

    paired_by_alias: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for alias, pair in pair_entries:
        paired_by_alias[alias].append(pair)

    summary = {
        "sequence_reference_occurrences": len(refs),
        "unique_sequence_keys": len({key for _, key in refs}),
        "paired_alias_entry_occurrences": len(pair_entries),
        "unique_paired_aliases": len(paired_by_alias),
        "ambiguous_alias_groups": ambiguous_groups,
        "ambiguous_sequence_reference_occurrences": ambiguous_refs,
        "unassigned_sequence_reference_occurrences": len(refs) - len(assigned_ref_positions),
        "unmatched_resource_like_token_count": len(resource_like_unmatched),
    }
    return summary, paired_by_alias


def summarize_directional_alias_regions(
    go_data: bytes,
    sequence_keys: tuple[str, ...] | list[str] | set[str] | frozenset[str],
    regions: tuple[tuple[int, int], tuple[int, int]],
) -> dict:
    """Summarize two owner-selected component regions without returning private labels."""
    if type(go_data) is not bytes or not 1 <= len(go_data) <= MAX_GO_BYTES:
        raise SequenceAliasCensusError("Invalid GO data size")
    if not isinstance(sequence_keys, (tuple, list, set, frozenset)):
        raise SequenceAliasCensusError("Sequence key collection is invalid")
    keys = tuple(sequence_keys)
    if (not 1 <= len(keys) <= MAX_SEQUENCE_KEYS
            or any(not isinstance(key, str) or not key for key in keys)
            or len(set(keys)) != len(keys)):
        raise SequenceAliasCensusError("Sequence keys are empty, duplicated, or excessive")
    if not isinstance(regions, tuple) or len(regions) != 2:
        raise SequenceAliasCensusError("Exactly two component regions are required")

    ordered_regions = []
    for region in regions:
        if (not isinstance(region, tuple) or len(region) != 2
                or type(region[0]) is not int or type(region[1]) is not int):
            raise SequenceAliasCensusError("Region bounds must be integer pairs")
        start, end = region
        if not 0 <= start < end <= len(go_data) or end - start > MAX_REGION_BYTES:
            raise SequenceAliasCensusError("Component region bounds are invalid")
        ordered_regions.append((start, end))
    if ordered_regions[0][1] > ordered_regions[1][0]:
        raise SequenceAliasCensusError("Component regions overlap or are out of order")

    keyset = frozenset(keys)
    summaries = []
    pair_maps = []
    for start, end in ordered_regions:
        summary, pairs = _summarize_region(go_data, keyset, start, end)
        summaries.append(summary)
        pair_maps.append(pairs)

    left, right = pair_maps
    shared = set(left) & set(right)
    comparable = [alias for alias in shared if len(left[alias]) == 1 and len(right[alias]) == 1]
    same = sum(left[alias][0] == right[alias][0] for alias in comparable)
    different = len(comparable) - same
    duplicated_shared = sum(
        len(left[alias]) != 1 or len(right[alias]) != 1 for alias in shared
    )

    return {
        "classification": "private_directional_sequence_alias_census",
        "region_count": 2,
        "regions": summaries,
        "cross_region": {
            "shared_paired_aliases": len(shared),
            "comparable_unique_aliases": len(comparable),
            "same_resource_pair_count": same,
            "different_resource_pair_count": different,
            "shared_aliases_with_duplicate_pair_entries": duplicated_shared,
        },
        "both_regions_have_no_unassigned_sequence_references": all(
            item["unassigned_sequence_reference_occurrences"] == 0 for item in summaries
        ),
        "all_resource_like_tokens_match_sequence_index": all(
            item["unmatched_resource_like_token_count"] == 0 for item in summaries
        ),
        "alias_labels_sequence_keys_offsets_and_original_bytes_exported": False,
    }


def audit_private_directional_sequence_aliases(
    ipa: Path, regions: tuple[tuple[int, int], tuple[int, int]],
) -> dict:
    """Audit two caller-bounded component regions in the owner-held IPA."""
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP member count")
        index = {}
        for info in infos:
            if info.filename in index:
                raise ValueError("Duplicate original ZIP member")
            index[info.filename] = info
        go_data = {}
        repositories = {}
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            go_data[screen] = _safe_read(
                archive, index.get(root + "go/default"), MAX_GO_BYTES
            )
            repositories[screen] = _safe_read(
                archive, index.get(root + "meta/SpriteSeqData.repo"), MAX_REPO_BYTES
            )
    if go_data[SCREENS[0]] != go_data[SCREENS[1]]:
        raise SequenceAliasCensusError("Paired GO default data differ across source packs")
    if repositories[SCREENS[0]] != repositories[SCREENS[1]]:
        raise SequenceAliasCensusError("Paired SpriteSequence repositories differ")
    rows = parse_sprite_repository(
        repositories[SCREENS[0]],
        expected_label="SpriteSeqData",
        expected_wad="sprite/SpriteSeqData.wad",
    )
    keys = tuple(row.key for row in rows)
    return summarize_directional_alias_regions(go_data[SCREENS[0]], keys, regions)


def _parse_region(value: str) -> tuple[int, int]:
    try:
        first, second = value.split(":", 1)
        return int(first, 10), int(second, 10)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("Region must be START:END decimal offsets") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--region", action="append", required=True, type=_parse_region,
                        help="private byte window START:END; provide exactly two regions")
    args = parser.parse_args(argv)
    if len(args.region) != 2:
        parser.error("exactly two --region values are required")
    report = audit_private_directional_sequence_aliases(args.ipa, tuple(args.region))
    destination = private_output_path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Private directional sequence alias census complete; aggregate-only report saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
