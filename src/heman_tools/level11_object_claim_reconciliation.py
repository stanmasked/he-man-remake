"""Reconcile separately supplied private Level1-1 object/contact claims.

A matching hash proves integrity of LOCAL bytes, not their origin. Two
matching human-authored role claims are consistency, NOT original iOS proof.
Does not export source files, hashes, positions, or C99 binding tables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from .frame_alignment import _private_path
from .level11_event_binding_preflight import (
    LEVEL_KEY, ROLES, assess_event_bindings,
)

MAX_JSON = 1_000_000
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
RECORD_KEYS = {
    "role", "native_event_index", "source_object_digest",
    "artifact_file", "artifact_sha256", "original_contact_verified",
}
BUNDLE_KEYS = {
    "schema_version", "level_key", "channel", "claims",
    "original_ios_provenance_authenticated",
    "automatic_event_bindings_permitted",
}
CHANNELS = ("resource_candidate", "observation_annotation")
EXTENSIONS = {".json", ".png", ".bin"}


def _sha(value: object, label: str) -> str:
    if type(value) is not str or not DIGEST.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{label} must be a nonzero lowercase SHA-256 hex digest")
    return value


def _artifact_file(root: Path, relative: object) -> Path:
    if (type(relative) is not str or not 1 <= len(relative) <= 180
            or "\\" in relative or relative.startswith("/")
            or not all(ch.isprintable() for ch in relative)):
        raise ValueError("private evidence path is invalid")
    requested = Path(relative)
    if any(part in ("..", ".", "") for part in requested.parts):
        raise ValueError("private evidence path traversal rejected")
    if requested.suffix not in EXTENSIONS:
        raise ValueError("private evidence extension must be json/png/bin")
    source = root / requested
    # Check all components, not just final file, against symlinks.
    node = root
    if root.is_symlink():
        raise ValueError("private evidence root cannot be a symlink")
    for part in requested.parts:
        node = node / part
        if node.is_symlink():
            raise ValueError("private evidence symlink rejected")
    resolved = source.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("private evidence must remain in local_reports")
    if (not resolved.is_file() or
            not 1 <= resolved.stat().st_size <= MAX_EVIDENCE_BYTES):
        raise ValueError("private evidence missing or exceeds size bound")
    return resolved


def _verified_artifact(root: Path, relative: object, expected: object) -> Path:
    path = _artifact_file(root, relative)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != _sha(expected, "artifact sha256"):
        raise ValueError("private evidence artifact checksum mismatch")
    return path


def _role_indexes(native: dict) -> dict:
    # The actual kind/count/index validation is performed by Stage109's
    # assessor before this helper reads the only already-checked roles.
    return {row["role"]: row["event_index"] for row in native["roles"]}


def _bundle(bundle: dict, channel: str, expected_indices: dict,
            root: Path, consumed_paths: set, consumed_digests: set) -> dict:
    if not isinstance(bundle, dict) or set(bundle) != BUNDLE_KEYS:
        raise ValueError("invalid private correspondence claim schema")
    if (type(bundle["schema_version"]) is not int or
            bundle["schema_version"] != 1 or
            bundle["level_key"] != LEVEL_KEY or
            bundle["channel"] != channel):
        raise ValueError("wrong original level, version, or evidence channel")
    if (bundle["original_ios_provenance_authenticated"] is not False or
            bundle["automatic_event_bindings_permitted"] is not False):
        raise ValueError("a private claim cannot assert original-source authenticity")
    claims = bundle["claims"]
    if not isinstance(claims, list) or len(claims) != len(ROLES):
        raise ValueError("all three distinct object claims required")
    result = {}
    for record in claims:
        if not isinstance(record, dict) or set(record) != RECORD_KEYS:
            raise ValueError("private object claim contains forbidden or missing fields")
        role = record["role"]
        if type(role) is not str or role not in ROLES or role in result:
            raise ValueError("duplicate or unknown object role")
        idx = record["native_event_index"]
        if type(idx) is not int or idx != expected_indices[role]:
            raise ValueError("object role differs from Stage109 native event mapping")
        if record["original_contact_verified"] is not False:
            raise ValueError("unverified original gameplay contact cannot be asserted")
        object_digest = _sha(record["source_object_digest"], "source object digest")
        artifact_digest = _sha(record["artifact_sha256"], "artifact sha256")
        source = _verified_artifact(root, record["artifact_file"],
                                    artifact_digest)
        if source in consumed_paths:
            raise ValueError("evidence artifact reused across roles/channels")
        if artifact_digest in consumed_digests:
            raise ValueError("identical evidence bytes reused across claims")
        consumed_paths.add(source)
        consumed_digests.add(artifact_digest)
        result[role] = object_digest
    if set(result) != set(ROLES) or len(set(result.values())) != len(ROLES):
        raise ValueError("source object IDs must be unique across all three roles")
    return result


def assess_private_correspondence(
    readiness: dict, native: dict, resource: dict,
    observation: dict, root: Path,
) -> dict:
    stage109 = assess_event_bindings(readiness, native)
    if not stage109["native_event_table_consistent"]:
        raise ValueError("native Level1-1 role preflight did not pass")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("private evidence root unavailable")
    indexes = _role_indexes(native)
    consumed = set()
    consumed_digests = set()
    first = _bundle(resource, CHANNELS[0], indexes, root, consumed,
                    consumed_digests)
    second = _bundle(observation, CHANNELS[1], indexes, root, consumed,
                     consumed_digests)
    if first != second:
        raise ValueError("resource and observation source-object identities disagree")
    # No IDs/hashes/coordinates, filenames or indexes in report or stdout.
    return {
        "schema_version": 1,
        "intended_level": LEVEL_KEY,
        "stage109_event_role_types_consistent": True,
        "private_claim_channels_structurally_consistent": True,
        "local_evidence_artifacts_integrity_checked": len(consumed),
        "distinct_matching_object_claims": len(first),
        "source_readiness_structurally_complete": stage109[
            "source_readiness_structurally_complete"],
        "original_ios_source_object_ownership_authenticated": False,
        "original_ios_contact_timing_authenticated": False,
        "original_geometry_verified": False,
        "automatic_collision_export_permitted": False,
        "switch_original_level_integration_permitted": False,
        "blockers": [
            "independent_original_source_provenance_not_authenticated",
            "original_ios_capture_contacts_not_authenticated",
            "original_collision_and_camera_geometry_not_verified",
            "manual_private_evidence_review_required",
        ],
    }


def _read(path: Path) -> dict:
    source = _private_path(path)
    if not source.is_file() or source.stat().st_size > MAX_JSON:
        raise ValueError("private JSON claim unavailable or oversized")
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("private claim must contain JSON object")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("readiness", "native", "resource", "observation", "out"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args(argv)
    paths = [_private_path(getattr(args, key)) for key in
             ("readiness", "native", "resource", "observation", "out")]
    if len(set(paths)) != len(paths):
        raise ValueError("private inputs/outputs cannot share paths")
    result = assess_private_correspondence(
        *[_read(path) for path in paths[:4]],
        root=Path.cwd() / "local_reports")
    paths[-1].parent.mkdir(parents=True, exist_ok=True)
    paths[-1].write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                         encoding="utf-8")
    print("PASS: two local object-claim channels and six evidence files "
          "consistent; original iOS provenance UNVERIFIED; import DENIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
