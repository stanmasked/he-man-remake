"""Stage164: same-length decoy controls for source-private sprite-cut lexical hits.

Stage163's exact indexed cut-name anchors are lexical observations only.
Here, synthetic *unregistered* cut-like tokens are derived from the
private source index in memory (same UTF-16 length and printable ASCII
framing) to form a specificity control. Decoys are guaranteed absent
from the index, but need not be absent from arbitrary opaque bodies.

Return ONLY coarse aggregate record counts. Neither the original names
nor the constructed decoy strings, raw bytes, offsets, per-record
values, token positions or output from private reports may be
published. Decoy comparison is not statistical proof of true frames.
All public tests use invented source packs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, MAX_MEMBERS, _safe_read
from .sprite_repo_wad_index import (
    SCREENS, MAX_REPO_BYTES, MAX_WAD_BYTES, SpriteIndexFormatError,
    _text, parse_sprite_repository,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from .sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD, _source_token
from .sprite_sequence_failure_strata import _PREFIX_GROUPS, _COUNT_GROUPS, _count_group
from .sprite_sequence_cut_anchor_scan import (
    _FIRST_CUT, _packed_cut_names, _scan_known_cut_anchors,
    summarize_sequence_lexical_cut_anchor_scan,
)
import struct

_HEAD = struct.Struct("<II")
_U32 = struct.Struct("<I")
_DECOY_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
_LABELS = (
    "known_first_cut_records",
    "real_later_cut_in_first_screen",
    "real_later_cut_in_second_screen",
    "real_later_cut_in_both_screens",
    "decoy_later_cut_in_first_screen",
    "decoy_later_cut_in_second_screen",
    "decoy_later_cut_in_both_screens",
    "real_and_decoy_later_tokens_in_same_screen",
    "real_later_anchor_lists_identical_across_screens",
)


def _same_length_decoy_keys(keys: frozenset[str]) -> frozenset[str]:
    """Generate one distinct non-indexed printable token per eligible key.

    This is a deterministic *diagnostic* choice, not a random control.
    If an unregistered same-size candidate cannot be allocated, fail
    closed rather than silently weakening the decoy control.
    """
    _packed_cut_names(keys)  # also requires a nonempty eligible registry
    eligible = sorted(k for k in keys if isinstance(k, str)
                      and 1 <= len(k) <= 128
                      and all(32 <= ord(c) <= 126 for c in k))
    chosen: set[str] = set()
    for key in eligible:
        for position in range(len(key)):
            for char in _DECOY_ALPHABET:
                replacement = key[:position] + char + key[position + 1:]
                if replacement != key and replacement not in keys and replacement not in chosen:
                    chosen.add(replacement)
                    break
            else:
                continue
            break
        else:
            raise SpriteIndexFormatError("No independent same-length decoy available")
    if len(chosen) != len(eligible):
        raise SpriteIndexFormatError("Incomplete same-length decoy registry")
    return frozenset(chosen)


def summarize_sequence_cut_decoy_controls(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Reconcile real anchors with Stage163, then compare private decoys."""
    parent = summarize_sequence_lexical_cut_anchor_scan(
        sequence_repos, sequence_wads, cut_repos
    )
    seq_index = parse_sprite_repository(
        sequence_repos[SCREENS[0]], expected_label="SpriteSeqData",
        expected_wad=WAD_PATH,
    )
    cut_index = parse_sprite_repository(
        cut_repos[SCREENS[0]], expected_label="SpriteCutData",
        expected_wad=CUT_WAD,
    )
    keys = frozenset(row.key for row in cut_index)
    decoys = _same_length_decoy_keys(keys)
    real_tokens = _packed_cut_names(keys)
    decoy_tokens = _packed_cut_names(decoys)
    pairs = [_intervals(seq_index, sequence_wads[s]) for s in SCREENS]
    counters = {
        group: {count: Counter() for count in _COUNT_GROUPS}
        for group in _PREFIX_GROUPS
    }

    for rec_a, rec_b in zip(*pairs):
        parsed = []
        for rec in (rec_a, rec_b):
            _, pos = _text(rec, 0)
            count = _HEAD.unpack_from(rec, pos)[1]
            if count == 0:
                parsed.append(None)
                continue
            word = _U32.unpack_from(rec, pos + 8)[0]
            at = pos + _FIRST_CUT
            status, initial = _source_token(rec, at)
            if status == "valid" and initial in keys:
                end = at + 2 + 2 * len(initial)
                real = _scan_known_cut_anchors(rec, end, real_tokens)
                fake = _scan_known_cut_anchors(rec, end, decoy_tokens)
                parsed.append((count, word, real, fake))
            else:
                parsed.append((count, word, None, None))

        if parsed[0] is None and parsed[1] is None:
            continue
        if parsed[0] is None or parsed[1] is None:
            raise SpriteIndexFormatError("Paired unknown count disagreement")
        ca, wa, real_a, fake_a = parsed[0]
        cb, wb, real_b, fake_b = parsed[1]
        if ca != cb or wa != wb or (real_a is None) != (real_b is None):
            raise SpriteIndexFormatError("Paired initial-cut evidence differs")
        if real_a is None:
            continue

        group = "first_u32_one" if wa == 1 else "first_u32_other"
        bucket = counters[group][_count_group(ca)]
        bucket["known_first_cut_records"] += 1
        real0, real1 = bool(real_a), bool(real_b)
        fake0, fake1 = bool(fake_a), bool(fake_b)
        bucket["real_later_cut_in_first_screen"] += real0
        bucket["real_later_cut_in_second_screen"] += real1
        bucket["real_later_cut_in_both_screens"] += real0 and real1
        bucket["decoy_later_cut_in_first_screen"] += fake0
        bucket["decoy_later_cut_in_second_screen"] += fake1
        bucket["decoy_later_cut_in_both_screens"] += fake0 and fake1
        bucket["real_and_decoy_later_tokens_in_same_screen"] += (
            (real0 and fake0) or (real1 and fake1)
        )
        bucket["real_later_anchor_lists_identical_across_screens"] += (
            real_a == real_b
        )

    controls = parent["candidate_lexical_anchor_status_by_firstword_and_count"]
    out = {}
    for group in _PREFIX_GROUPS:
        out[group] = {}
        for count in _COUNT_GROUPS:
            source = controls[group][count]
            classes = source["candidate_lexical_anchor_classes"]
            c = counters[group][count]
            expected_known = source["records"] - classes["initial_cut_name_missing"]
            if c["known_first_cut_records"] != expected_known:
                raise SpriteIndexFormatError("Stage163 known-first anchor totals differ")
            expected_real = (
                classes["one_candidate_with_later_cut_name"] +
                classes["multi_candidate_some_but_below_count"] +
                classes["multi_candidate_matches_count_minus_one"] +
                classes["multi_candidate_above_count_minus_one"]
            )
            if c["real_later_cut_in_first_screen"] != expected_real:
                raise SpriteIndexFormatError("Stage163 later-anchor totals differ")
            if c["real_later_anchor_lists_identical_across_screens"] != (
                source["later_anchor_lists_identical_across_packs"]
            ):
                raise SpriteIndexFormatError("Stage163 screen anchor parity differs")
            out[group][count] = {label: c[label] for label in _LABELS}

    return {
        "classification": "owner_private_sprite_lexical_same_length_decoy_controls",
        "control_registry": "one_deterministic_unregistered_same_length_token_per_eligible_indexed_cut_key",
        "eligible_indexed_cut_token_count": sum(
            len(v) for v in real_tokens.values()),
        "independently_generated_decoy_token_count": len(decoys),
        "controls_by_firstword_and_unknown_count": out,
        "real_anchors_reconciled_against_stage163": True,
        "decoy_hits_are_negative_control_observations_only": True,
        "null_results_prove_animation_frame_boundaries": False,
        "source_name_lists_header_values_byte_positions_or_decoys_exported": False,
        "original_frame_durations_or_playback_verified": False,
        "original_sprite_import_to_switch_enabled": False,
    }


def audit_private_sequence_cut_decoy_controls(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP members")
        lookup = {item.filename: item for item in infos}
        if len(lookup) != len(infos):
            raise ValueError("Duplicate original ZIP member")
        repos, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            prefix = PREFIX + screen + "/"
            repos[screen] = _safe_read(
                archive, lookup.get(prefix + REPO_PATH), MAX_REPO_BYTES)
            wads[screen] = _safe_read(
                archive, lookup.get(prefix + WAD_PATH), MAX_WAD_BYTES)
            cuts[screen] = _safe_read(
                archive, lookup.get(prefix + CUT_REPO), MAX_REPO_BYTES)
    return summarize_sequence_cut_decoy_controls(repos, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    target = private_output_path(args.out)
    summary = audit_private_sequence_cut_decoy_controls(args.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n",
                      encoding="utf-8")
    print("Owner-private sprite lexical decoy controls saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
