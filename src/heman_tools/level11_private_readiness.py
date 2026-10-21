"""Read-only private original Level 1-1 integration readiness preflight.

Never exports source level geometry or claims Android walkthrough == iOS 2.0.
Requires original private candidate reports *and* private binary resource
pair summary, and explicit manual evidence declarations. Every success
is structural only; actual iOS recording authentication is unavailable.
All paths and source-derived identities stay in local_reports/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .first_level_report_audit import audit_level_report_consistency
from .frame_alignment import _private_path
from .level_evidence_gate import assess_geometry_evidence

LEVEL = "MULevel1-1.lvl"
SCREEN_VARIANTS = ("screen-med", "screen-xlarge")
MAX_JSON_BYTES = 1_000_000
_PRIVATE_FIELDS = {"level", "candidate_map", "screen", "filename", "map"}


def _bounded_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0 or value > 1_000_000_000:
        raise ValueError(f"malformed private resource pair: {label}")
    return value


def _check_private_pair(pair: dict, *, level: str, map_name: str) -> dict:
    """Check report shape and precise level/map ID parity, NOT real source."""
    if not isinstance(pair, dict) or pair.get("schema_version") != 1:
        raise ValueError("invalid private level/map pair report")
    if pair.get("level") != level or pair.get("candidate_map") != map_name:
        raise ValueError("private pair targets a different level/map")
    if pair.get("screen_variants") != list(SCREEN_VARIANTS):
        raise ValueError("resource screen variants differ from expected pair")
    if any(pair.get(k) is not False for k in (
        "level_to_map_binding_verified", "collision_type_verified",
        "original_gameplay_trace_verified",
        "automatic_collision_export_permitted",
    )):
        raise ValueError("pair metadata falsely claims authenticated gameplay")
    selected = pair.get("selected_pairs")
    if not isinstance(selected, dict) or set(selected) != {"level", "map"}:
        raise ValueError("pair report must describe level and map binaries")
    all_equal = True
    for kind, item in selected.items():
        if not isinstance(item, dict):
            raise ValueError("malformed level/map binary pair")
        sizes = item.get("bytes_per_screen")
        headers = item.get("first_u32_per_screen")
        if not isinstance(sizes, dict) or not isinstance(headers, dict):
            raise ValueError("missing private screen pair metadata")
        if set(sizes) != set(SCREEN_VARIANTS) or set(headers) != set(SCREEN_VARIANTS):
            raise ValueError("pair metadata lacks one original screen variant")
        for screen in SCREEN_VARIANTS:
            if not 4 <= _bounded_int(sizes[screen], "file size") <= 16 * 1024 * 1024:
                raise ValueError("source pair file size outside parser bound")
            _bounded_int(headers[screen], "header value")
        if type(item.get("standard_header_observed")) is not bool:
            raise ValueError("pair header flag must be a boolean")
        if type(item.get("exact_bytes_equal")) is not bool:
            raise ValueError("pair byte-parity flag must be a boolean")
        all_equal &= item["exact_bytes_equal"]
    if type(pair.get("cross_pack_bytes_identical")) is not bool:
        raise ValueError("invalid aggregate pair equality flag")
    if pair["cross_pack_bytes_identical"] != all_equal:
        raise ValueError("individual and aggregate source pair equality disagree")
    return {
        "pair_report_consistent": True,
        "screen_pack_binary_parity_declared": all_equal,
        "source_resource_headers_observed": all(
            item["standard_header_observed"] for item in selected.values()
        ),
    }


def _capture_status(capture: dict | None) -> tuple[str, ...]:
    if capture is None:
        return ("original_ios_contact_capture_not_supplied",)
    if not isinstance(capture, dict) or capture.get("schema_version") != 1:
        raise ValueError("unrecognized private contact/capture join summary")
    for key in (
        "genuine_ios_capture_provenance_authenticated",
        "recorded_video_frames_decoded", "original_ios_frame_rate_established",
        "original_gameplay_physics_verified",
        "automatic_collision_export_permitted",
    ):
        if capture.get(key) is not False:
            raise ValueError("capture report cannot authenticate original gameplay")
    if type(capture.get("all_declarative_integrity_and_numeric_checks_met")) is not bool:
        raise ValueError("invalid capture structural completeness flag")
    return (
        ("capture_metadata_incomplete",)
        if not capture["all_declarative_integrity_and_numeric_checks_met"]
        else ("capture_metadata_only_original_frames_not_authenticated",)
    )


def assess_private_level11(
    links: dict, shapes: dict, collision: dict, pair: dict,
    manual_checks: dict, capture_join: dict | None = None,
) -> dict:
    """Deny automatic Switch-world conversion even for fabricated all-green declarations."""
    cross = audit_level_report_consistency(links, shapes, collision)
    if cross["level"] != LEVEL:
        raise ValueError("private reports do not describe the original Level 1-1")
    source_pair = _check_private_pair(
        pair, level=cross["level"], map_name=cross["candidate_map"],
    )
    manual = assess_geometry_evidence(manual_checks)
    blockers = []
    if not cross["single_exact_text_reference"]:
        blockers.append("map_identity_has_no_unique_candidate")
    if not cross["one_named_collision_layer"]:
        blockers.append("map_collision_layer_not_unique")
    if cross["shape_candidates_ambiguous"]:
        blockers.append("ambiguous_shape_object_matches")
    if not source_pair["source_resource_headers_observed"]:
        blockers.append("resource_format_header_not_confirmed")
    if not source_pair["screen_pack_binary_parity_declared"]:
        blockers.append("screen_variant_binary_differences_need_private_review")
    blockers.extend(
        "manual_" + name for name in manual["missing_evidence"]
    )
    blockers.extend(_capture_status(capture_join))
    blockers.append("source_original_ios_gameplay_not_independently_authenticated")
    if cross["automatic_collision_export_permitted"] is not False:
        raise ValueError("cross report incorrectly permits collision export")
    if manual["automatic_collision_export_permitted"] is not False:
        raise ValueError("manual checklist incorrectly permits collision export")

    # No original names, source paths, coordinates, IDs or copied art.
    return {
        "schema_version": 1,
        "intended_level": "original-level-1-1",
        "screen_variant_count": len(SCREEN_VARIANTS),
        "map_candidate_unique": cross["single_exact_text_reference"],
        "named_collision_layer_unique": cross["one_named_collision_layer"],
        "shape_object_candidates_ambiguous": (
            cross["shape_candidates_ambiguous"] > 0
        ),
        "resource_pair_schema_consistent": source_pair["pair_report_consistent"],
        "screen_pack_binary_parity_declared": (
            source_pair["screen_pack_binary_parity_declared"]
        ),
        "manual_checks_declared_complete": (
            manual["all_required_checks_recorded"]
        ),
        "blockers": list(dict.fromkeys(blockers)),
        "external_original_ios_frames_verified": False,
        "original_map_collision_semantics_verified": False,
        "original_asset_fidelity_verified": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
        "switch_original_level_import_permitted": False,
        "interpretation": (
            "Consistent private metadata cannot authenticate real iOS "
            "scene contacts or authorize conversion of commercial "
            "level assets. This is a structural preflight only."
        ),
    }


def _read_private(path: Path) -> dict:
    real = _private_path(path)
    if not real.is_file() or real.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("private report unavailable or exceeds byte bound")
    document = json.loads(real.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("private source summary must be a JSON object")
    return document


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("links", "shapes", "collision", "pair", "manual"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--captures", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    keys = ("links", "shapes", "collision", "pair", "manual")
    all_paths = [getattr(args, key) for key in keys]
    if args.captures is not None:
        all_paths.append(args.captures)
    all_paths.append(args.out)
    canonical = [_private_path(path) for path in all_paths]
    if len(set(canonical)) != len(canonical):
        raise ValueError("private input and output reports cannot share paths")
    inputs = [_read_private(path) for path in all_paths[:-1]]
    core = inputs[:5]
    capture_join = inputs[5] if args.captures else None
    result = assess_private_level11(*core, capture_join)
    out = canonical[-1]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print("Private Level 1-1 source audit completed: no game data exported; "
          "original iOS gameplay and automatic collision import UNVERIFIED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
