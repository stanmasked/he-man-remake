"""Stage212: private aggregate census of native TextureData sampling metadata."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .native_render_state_contract import (
    decode_texture_alpha_transform_flag,
    decode_texture_filter_mode,
    decode_texture_payload_selector,
    resolve_texture_sampling_state,
)
from .physics_shape_census import MAX_MEMBERS, PREFIX, SCREENS, _safe_read
from .sprite_cut_texture_image_graph import parse_texture_data_record
from .sprite_cut_wrap_bounds_audit import decode_texture_wrap_codes, texture_wrap_mode
from .sprite_repo_wad_index import MAX_REPO_BYTES, MAX_WAD_BYTES, parse_sprite_repository
from .sprite_wad_record_intervals import _intervals


class TextureSamplingCensusError(ValueError):
    """Invalid or inconsistent private TextureData sampling metadata."""


def _wrap_counts(codes: Counter) -> dict:
    return {
        "clamp_to_edge": codes["clamp_to_edge"],
        "repeat": codes["repeat"],
        "unrecognized": codes["unrecognized"],
    }


def audit_private_texture_sampling_modes(ipa: Path) -> dict:
    """Inspect all indexed TextureData records and return aggregate-only evidence."""
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA not found")
    with ZipFile(ipa, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise TextureSamplingCensusError("IPA member count exceeds safety limit")
        members = {}
        for info in infos:
            if info.filename in members:
                raise TextureSamplingCensusError("Duplicate IPA member name")
            members[info.filename] = info

        repo_bytes = {}
        wad_bytes = {}
        private_signatures = {}
        per_pack = {}
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            repo = _safe_read(
                archive, members.get(root + "meta/TextureData.repo"), MAX_REPO_BYTES
            )
            wad = _safe_read(
                archive, members.get(root + "textureData/TextureData.wad"), MAX_WAD_BYTES
            )
            rows = parse_sprite_repository(
                repo, expected_label="TextureData",
                expected_wad="textureData/TextureData.wad",
            )
            records = _intervals(rows, wad)
            filters = Counter()
            alpha_flags = Counter()
            payload_selectors = Counter()
            wraps_s = Counter()
            wraps_t = Counter()
            signatures = []
            mipmap_count = 0
            for entry, record in zip(rows, records):
                key, image_key, scalar_block = parse_texture_data_record(record)
                if key != entry.key or not image_key:
                    raise TextureSamplingCensusError(
                        "TextureData indexed record identity is invalid"
                    )
                code = decode_texture_filter_mode(scalar_block)
                alpha_flag = decode_texture_alpha_transform_flag(scalar_block)
                payload_selector = decode_texture_payload_selector(scalar_block)
                state = resolve_texture_sampling_state(code)
                wrap_s, wrap_t = decode_texture_wrap_codes(scalar_block)
                filters[state.filter_mode_name] += 1
                alpha_flags[alpha_flag] += 1
                payload_selectors[payload_selector] += 1
                wraps_s[texture_wrap_mode(wrap_s)] += 1
                wraps_t[texture_wrap_mode(wrap_t)] += 1
                mipmap_count += int(state.generate_mipmaps)
                # Names and scalar bytes stay in memory only, for pack comparison.
                signatures.append((key, image_key, scalar_block))
            repo_bytes[screen] = repo
            wad_bytes[screen] = wad
            private_signatures[screen] = tuple(signatures)
            per_pack[screen] = {
                "texture_record_count": len(rows),
                "filter_mode_counts": {
                    "nearest": filters["nearest"],
                    "linear": filters["linear"],
                    "linear_mipmap_nearest": filters["linear_mipmap_nearest"],
                },
                "alpha_transform_flag_counts": {
                    "disabled": alpha_flags[0],
                    "enabled": alpha_flags[1],
                },
                "image_payload_selector_counts": {
                    "png_path": payload_selectors[0],
                    "alternate_path": payload_selectors[1],
                },
                "wrap_s_mode_counts": _wrap_counts(wraps_s),
                "wrap_t_mode_counts": _wrap_counts(wraps_t),
                "textures_requiring_mipmaps": mipmap_count,
                "all_filter_modes_supported": True,
                "all_alpha_transform_flags_boolean": True,
                "all_payload_selectors_supported": True,
                "all_wrap_modes_recognized": (
                    wraps_s["unrecognized"] == 0 and wraps_t["unrecognized"] == 0
                ),
            }

    repo_indexes_match = repo_bytes[SCREENS[0]] == repo_bytes[SCREENS[1]]
    wad_bytes_match = wad_bytes[SCREENS[0]] == wad_bytes[SCREENS[1]]
    records_match = private_signatures[SCREENS[0]] == private_signatures[SCREENS[1]]
    counts_match = per_pack[SCREENS[0]]["filter_mode_counts"] == per_pack[SCREENS[1]]["filter_mode_counts"]
    alpha_flags_match = per_pack[SCREENS[0]]["alpha_transform_flag_counts"] == per_pack[SCREENS[1]]["alpha_transform_flag_counts"]
    payload_selectors_match = per_pack[SCREENS[0]]["image_payload_selector_counts"] == per_pack[SCREENS[1]]["image_payload_selector_counts"]
    wraps_match = (
        per_pack[SCREENS[0]]["wrap_s_mode_counts"] == per_pack[SCREENS[1]]["wrap_s_mode_counts"]
        and per_pack[SCREENS[0]]["wrap_t_mode_counts"] == per_pack[SCREENS[1]]["wrap_t_mode_counts"]
    )
    all_nearest = all(
        row["filter_mode_counts"]["nearest"] == row["texture_record_count"]
        and row["filter_mode_counts"]["linear"] == 0
        and row["filter_mode_counts"]["linear_mipmap_nearest"] == 0
        and row["textures_requiring_mipmaps"] == 0
        for row in per_pack.values()
    )
    all_alpha_disabled = all(
        row["alpha_transform_flag_counts"]["disabled"] == row["texture_record_count"]
        and row["alpha_transform_flag_counts"]["enabled"] == 0
        for row in per_pack.values()
    )
    all_payloads_png = all(
        row["image_payload_selector_counts"]["png_path"] == row["texture_record_count"]
        and row["image_payload_selector_counts"]["alternate_path"] == 0
        for row in per_pack.values()
    )
    all_wraps_recognized = all(row["all_wrap_modes_recognized"] for row in per_pack.values())
    return {
        "classification": "private_native_texture_sampling_mode_census",
        "texture_record_count_per_pack": per_pack[SCREENS[0]]["texture_record_count"],
        "per_pack": per_pack,
        "texture_repository_indexes_match": repo_indexes_match,
        "texture_wad_bytes_match": wad_bytes_match,
        "texture_record_identity_and_sampling_metadata_match": records_match,
        "filter_mode_counts_match": counts_match,
        "alpha_transform_flag_counts_match": alpha_flags_match,
        "image_payload_selector_counts_match": payload_selectors_match,
        "wrap_mode_counts_match": wraps_match,
        "all_wrap_modes_recognized": all_wraps_recognized,
        "all_source_textures_use_nearest_filtering_without_mipmaps": all_nearest,
        "all_source_textures_alpha_transform_disabled": all_alpha_disabled,
        "all_source_textures_use_png_payload_path": all_payloads_png,
        "all_source_textures_use_supported_filter_modes": True,
        "paired_sampling_metadata_match": all(
            (repo_indexes_match, wad_bytes_match, records_match, counts_match,
             alpha_flags_match, payload_selectors_match, wraps_match,
             all_wraps_recognized)
        ),
        "original_runtime_pixel_parity_verified": False,
        "private_resource_details_exported": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    report = audit_private_texture_sampling_modes(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("Private TextureData sampling census complete; aggregate report saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
