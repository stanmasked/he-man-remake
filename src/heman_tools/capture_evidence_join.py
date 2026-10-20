"""Bind private contact traces, timing metadata and capture files by ID.

This is strictly a structural evidence audit. Neither file hashes nor
matching source labels authenticate iOS gameplay or collision semantics.
No original files, video bytes or measured coordinates are exported.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .capture_media_receipts import audit_capture_manifest, PLATFORMS
from .capture_timing_audit import audit_timing
from .contact_scenarios import SCENARIOS, validate_scenario_suite
from .frame_alignment import _private_path

MAX_INPUT_BYTES = 6_000_000
MAX_SCENARIOS = len(SCENARIOS)


def _indexed_traces(source: object, label: str) -> dict:
    if not isinstance(source, dict) or not isinstance(source.get("traces"), list):
        raise ValueError(f"{label} must contain a five-trace object")
    items = source["traces"]
    if len(items) != MAX_SCENARIOS:
        raise ValueError(f"{label} must have exactly five distinct scenarios")
    result = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{label} contains a non-object trace")
        key = item.get("scenario_id")
        if type(key) is not str or key not in SCENARIOS:
            raise ValueError(f"{label} contains an invalid scenario")
        if key in result:
            raise ValueError(f"{label} repeats a scenario")
        result[key] = item
    if set(result) != set(SCENARIOS):
        raise ValueError(f"{label} has missing scenarios")
    return result


def audit_evidence_bundle(media_manifest: dict, timing_suite: dict,
                          contact_suite: dict, private_root: Path) -> dict:
    """Require one matching ID across all three private capture descriptions.

    When every synthetic input is aligned, a purely structural pass is
    possible but actual-source provenance remains explicitly UNVERIFIED.
    """
    if not isinstance(media_manifest, dict):
        raise ValueError("media manifest must be an object")
    contact = _indexed_traces(contact_suite, "contact suite")
    timings = _indexed_traces(timing_suite, "timing suite")
    captures = media_manifest.get("captures")
    if not isinstance(captures, list):
        raise ValueError("media manifest requires capture entries")
    if len(captures) != 2 * MAX_SCENARIOS:
        raise ValueError("evidence join requires ten declared media captures")

    manifest_by_pair = {}
    seen_ids = set()
    for item in captures:
        if not isinstance(item, dict):
            raise ValueError("invalid capture-manifest row")
        scene = item.get("scenario_id")
        platform = item.get("platform")
        if (type(scene) is not str or scene not in SCENARIOS
                or type(platform) is not str or platform not in PLATFORMS):
            raise ValueError("invalid media scenario/platform")
        key = (scene, platform)
        if key in manifest_by_pair:
            raise ValueError("duplicate media capture pair")
        capture_id = item.get("capture_id")
        if (type(capture_id) is not str or not 1 <= len(capture_id) <= 128
                or capture_id in seen_ids):
            raise ValueError("missing, repeated or invalid media capture ID")
        manifest_by_pair[key] = capture_id
        seen_ids.add(capture_id)

    media_report = audit_capture_manifest(media_manifest, private_root)
    contact_report = validate_scenario_suite(contact_suite)
    by_scenario = {}
    all_timing_passed = True
    seen_timing_ids = set()
    for scene in SCENARIOS:
        paired_contact = contact[scene]
        paired_timing = timings[scene]
        timing_report = audit_timing(paired_timing)
        all_timing_passed = (
            all_timing_passed and
            timing_report["timing_consistent_under_supplied_metadata"])
        for side, platform in (("reference", "ios"), ("candidate", "switch")):
            media_id = manifest_by_pair[(scene, platform)]
            contact_source = paired_contact.get(side)
            timing_source = paired_timing.get(side)
            if (not isinstance(contact_source, dict)
                    or not isinstance(timing_source, dict)):
                raise ValueError("missing paired capture identity")
            ids = (media_id, contact_source.get("capture_id"),
                   timing_source.get("capture_id"))
            if any(type(value) is not str for value in ids) or len(set(ids)) != 1:
                raise ValueError(
                    f"media, contact and timing capture IDs differ: {scene}:{platform}")
            if timing_source.get("platform") != platform:
                raise ValueError("timing data belong to wrong platform")
            if (timing_source.get("evidence_kind") !=
                    contact_source.get("evidence_kind")):
                raise ValueError(
                    "contact and timing evidence labels disagree")
            if media_id in seen_timing_ids:
                raise ValueError("a timing capture ID is reused")
            seen_timing_ids.add(media_id)
        by_scenario[scene] = {
            "timing_metadata_consistent": timing_report[
                "timing_consistent_under_supplied_metadata"],
            "timing_blockers": timing_report["structural_blockers"],
            "contact_and_numeric_contract_met": contact_report["scenarios"][
                scene]["protocol_and_numeric_consistency_on_supplied_records"],
            "capture_identity_matched_across_three_sources": True,
        }
    success = (
        media_report["all_ten_unique_files_present_without_blockers"]
        and contact_report["numerical_and_event_contracts_all_met"]
        and all_timing_passed)
    return {
        "schema_version": 1,
        "expected_capture_count": 10,
        "present_media_files": media_report["present_media_files"],
        "media_integrity_blockers": media_report["structural_blockers"],
        "by_scenario": by_scenario,
        "all_declarative_integrity_and_numeric_checks_met": success,
        "genuine_ios_capture_provenance_authenticated": False,
        "recorded_video_frames_decoded": False,
        "original_ios_frame_rate_established": False,
        "cross_device_absolute_clock_synchronized": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
        "interpretation": (
            "Three self-declared private inputs agree on capture identifiers "
            "and numeric contracts. File content, provenance, contact labels, "
            "real timestamps, source iOS frame rate and physical behavior "
            "are NOT authenticated."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--contacts", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = [_private_path(p) for p in
             (args.media, args.timing, args.contacts, args.out)]
    if len(set(paths)) != 4:
        raise ValueError("all four private input/output paths must differ")
    for source in paths[:3]:
        if source.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("private evidence JSON exceeds input size bound")
    media, timing, contact = [
        json.loads(path.read_text(encoding="utf-8")) for path in paths[:3]
    ]
    report = audit_evidence_bundle(media, timing, contact,
                                   Path.cwd() / "local_reports")
    target = paths[3]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Private evidence joined by IDs; original-game provenance unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
