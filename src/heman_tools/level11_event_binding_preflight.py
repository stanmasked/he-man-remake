"""Fail-closed, local-only Level 1-1 event-role binding preflight.

Compares a redacted Stage103 structural readiness report with a PRIVATE
proposed native event table and explicit lore roles. No coordinates,
commercial level art, object labels, or proprietary map content leaves
local_reports/. This is a consistency test, NOT original iOS proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .frame_alignment import _private_path

MAX_BYTES = 1_000_000
LEVEL_KEY = "original-level-1-1"
ROLES = {
    "left_gate": "HM_TRIGGER",
    "skeletor_bio": "HM_PICKUP",
    "concept_art_09": "HM_PICKUP",
}
EVENT_KINDS = {"HM_TRIGGER", "HM_PICKUP", "HM_CHECKPOINT", "HM_HAZARD", "HM_EXIT"}
READY_FLAGS = (
    "external_original_ios_frames_verified",
    "original_map_collision_semantics_verified",
    "original_asset_fidelity_verified",
    "original_gameplay_physics_verified",
    "automatic_collision_export_permitted",
    "switch_original_level_import_permitted",
)
MANIFEST_FLAGS = (
    "world_coordinate_transform_verified",
    "original_collision_semantics_verified",
    "ios_capture_contact_timing_verified",
    "automatic_gameplay_enable_permitted",
)
TOP_KEYS = {
    "schema_version", "level_key", "native_world_event_count",
    "events", "roles", *MANIFEST_FLAGS,
}


def _integer(value: object, label: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer between {low} and {high}")
    return value


def _ready_summary(data: dict) -> tuple[bool, int]:
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or data.get("intended_level") != LEVEL_KEY):
        raise ValueError("not an original Level 1-1 private readiness report")
    if any(data.get(key) is not False for key in READY_FLAGS):
        raise ValueError("unverified source-readiness booleans cannot grant iOS authority")
    fields = (
        "map_candidate_unique", "named_collision_layer_unique",
        "shape_object_candidates_ambiguous",
        "resource_pair_schema_consistent",
        "screen_pack_binary_parity_declared",
        "manual_checks_declared_complete",
    )
    if any(type(data.get(key)) is not bool for key in fields):
        raise ValueError("malformed source-readiness structural flags")
    blockers = data.get("blockers")
    if (not isinstance(blockers, list) or len(blockers) > 64
            or any(not isinstance(item, str) or len(item) > 128
                   for item in blockers)):
        raise ValueError("invalid private readiness blockers")
    # Never echo raw blocker values: the provided private report could be
    # accidentally edited to include filenames, paths or source addresses.
    structurally_complete = (
        data["map_candidate_unique"]
        and data["named_collision_layer_unique"]
        and not data["shape_object_candidates_ambiguous"]
        and data["resource_pair_schema_consistent"]
        and data["screen_pack_binary_parity_declared"]
        and data["manual_checks_declared_complete"]
    )
    return structurally_complete, len(blockers)


def assess_event_bindings(readiness: dict, manifest: dict) -> dict:
    source_complete, existing_blockers = _ready_summary(readiness)
    if not isinstance(manifest, dict) or set(manifest) != TOP_KEYS:
        raise ValueError("unexpected private native event manifest schema")
    if manifest["schema_version"] != 1 or manifest["level_key"] != LEVEL_KEY:
        raise ValueError("event bindings are for a different level")
    if any(manifest[key] is not False for key in MANIFEST_FLAGS):
        raise ValueError("private manifest cannot independently authenticate original iOS")
    count = _integer(manifest["native_world_event_count"], "native event count", 3, 32)
    events = manifest["events"]
    roles = manifest["roles"]
    if not isinstance(events, list) or len(events) != count:
        raise ValueError("event table must contain every native world event")
    if not isinstance(roles, list) or len(roles) != len(ROLES):
        raise ValueError("exactly three Level 1-1 event roles are required")

    kinds = []
    for position, event in enumerate(events):
        if not isinstance(event, dict) or set(event) != {"index", "kind"}:
            raise ValueError("native event descriptor cannot include geometry or arbitrary keys")
        if _integer(event["index"], "event index", 0, count - 1) != position:
            raise ValueError("native world indices must be contiguous and ordered")
        if type(event["kind"]) is not str or event["kind"] not in EVENT_KINDS:
            raise ValueError("unsupported native event kind")
        kinds.append(event["kind"])

    role_to_index = {}
    for entry in roles:
        if not isinstance(entry, dict) or set(entry) != {
            "role", "event_index", "event_kind", "source_contact_verified"
        }:
            raise ValueError("private role descriptor is malformed")
        role = entry["role"]
        if type(role) is not str or role not in ROLES or role in role_to_index:
            raise ValueError("duplicate or unknown Level 1-1 event role")
        if entry["source_contact_verified"] is not False:
            raise ValueError("unverified original iOS event ownership cannot be asserted")
        number = _integer(entry["event_index"], "role event index", 0, count - 1)
        if entry["event_kind"] != ROLES[role] or kinds[number] != ROLES[role]:
            raise ValueError("gate/lore role does not match real native event kind")
        role_to_index[role] = number
    if set(role_to_index) != set(ROLES):
        raise ValueError("a required gate or lore role is missing")
    if len(set(role_to_index.values())) != len(ROLES):
        raise ValueError("two distinct lore roles cannot bind the same event index")

    blockers = ["original_event_contact_provenance_unverified",
                "original_ios_camera_and_collision_semantics_unverified",
                "manual_source_review_required"]
    if not source_complete:
        blockers.insert(0, "stage103_source_readiness_incomplete")

    # Deliberately omit raw index mappings and any private filename: this
    # is a structural result, never an exportable mapping or game level.
    return {
        "schema_version": 1,
        "intended_level": LEVEL_KEY,
        "source_readiness_structurally_complete": source_complete,
        "source_readiness_blocker_count": existing_blockers,
        "native_event_table_consistent": True,
        "distinct_correctly_typed_gate_and_lore_roles": True,
        "native_event_count": count,
        "private_source_contacts_authenticated": False,
        "original_ios_level_geometry_verified": False,
        "automatic_collision_export_permitted": False,
        "switch_original_level_integration_permitted": False,
        "blockers": blockers,
    }


def _read(path: Path) -> dict:
    location = _private_path(path)
    if not location.is_file() or location.stat().st_size > MAX_BYTES:
        raise ValueError("private JSON report is missing or oversized")
    data = json.loads(location.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("private report must contain a JSON object")
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    locations = [
        _private_path(args.readiness),
        _private_path(args.events),
        _private_path(args.out),
    ]
    if len(set(locations)) != 3:
        raise ValueError("private input and output reports cannot share paths")
    result = assess_event_bindings(_read(args.readiness), _read(args.events))
    locations[2].parent.mkdir(parents=True, exist_ok=True)
    locations[2].write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                            encoding="utf-8")
    print("PASS: private Level 1-1 event-table structural preflight; "
          "original iOS contact provenance NOT verified; Switch import DENIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
