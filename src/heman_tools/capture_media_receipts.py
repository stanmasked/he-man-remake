"""Read-only local capture file inventory; file integrity is NOT provenance.

Public repository contains no original gameplay video or proprietary files.
The private report stores SHA-256 fingerprints; never commit those reports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat

from .contact_scenarios import SCENARIOS

PLATFORMS = ("ios", "switch")
FORMATS = (".mov", ".mp4", ".mkv")
SOURCE_LABELS = {
    "ios": frozenset(("ios_device", "ios_emulator", "synthetic_fixture")),
    "switch": frozenset(("switch_hardware", "switch_emulator",
                         "synthetic_fixture")),
}
MAX_MANIFEST_BYTES = 256_000
MAX_MEDIA_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
READ_CHUNK = 1024 * 1024


def _name(value: object, label: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or not value.isprintable() or
            any(ord(c) < 32 for c in value)):
        raise ValueError(f"invalid {label}")
    return value


def _private_root(root: Path) -> Path:
    if root.is_symlink():
        raise ValueError("local_reports root must not be a symlink")
    return root.resolve()


def _capture_file(root: Path, relative: object) -> Path:
    """Only one immediate regular file in ignored local_reports/captures/."""
    if (not isinstance(relative, str) or not relative.startswith("captures/")
            or relative.count("/") != 1 or "\\" in relative
            or len(relative) > 250):
        raise ValueError("capture file must be a simple captures/ basename")
    basename = relative[len("captures/"):]
    if (not basename or basename.startswith(".")
            or basename in (".", "..")
            or any(c not in "abcdefghijklmnopqrstuvwxyz"
                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                   for c in basename)
            or Path(basename).suffix.lower() not in FORMATS):
        raise ValueError("invalid recording file basename or extension")
    capture_dir = root / "captures"
    if capture_dir.is_symlink():
        raise ValueError("capture directory must not be a symlink")
    candidate = capture_dir / basename
    if candidate.is_symlink():
        raise ValueError("recording may not be a symbolic link")
    if not candidate.resolve().is_relative_to(root):
        raise ValueError("recording leaves private storage root")
    return candidate


def _digest_regular_file(path: Path) -> tuple[int, str] | None:
    """Hash bounded private clip bytes without publishing or decoding video."""
    if not path.exists():
        return None
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError("recording must be a regular file")
    n = path.stat().st_size
    if not 16 <= n <= MAX_MEDIA_BYTES:
        raise ValueError("recording has invalid or excessive byte count")
    digest = hashlib.sha256()
    read = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(READ_CHUNK)
            if not chunk:
                break
            read += len(chunk)
            if read > MAX_MEDIA_BYTES:
                raise ValueError("recording grew beyond read bound")
            digest.update(chunk)
    if read != n:
        raise ValueError("recording changed during hashing")
    return read, digest.hexdigest()


def audit_capture_manifest(manifest: dict, private_root: Path) -> dict:
    """Inventory ten distinct private media clips for the five protocols.

    A hash does not authenticate the actor, timestamps, input synchronization
    or whether the bytes contain a valid gameplay recording.
    """
    if (not isinstance(manifest, dict)
            or type(manifest.get("protocol_version")) is not int
            or manifest["protocol_version"] != 1):
        raise ValueError("unsupported capture manifest version")
    entries = manifest.get("captures")
    if not isinstance(entries, list) or len(entries) > 10:
        raise ValueError("manifest must list at most ten captures")
    root = _private_root(private_root)
    observed = {}
    used_ids = set()
    used_paths = set()
    hashes = {}
    total_bytes = 0
    files = {}
    warnings = []
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("capture record must be an object")
        scenario = row.get("scenario_id")
        platform = row.get("platform")
        if (type(scenario) is not str or scenario not in SCENARIOS
                or type(platform) is not str or platform not in PLATFORMS):
            raise ValueError("unsupported scenario/platform combination")
        pair = (scenario, platform)
        if pair in observed:
            raise ValueError("duplicate scenario/platform recording")
        capture_id = _name(row.get("capture_id"), "capture_id")
        if capture_id in used_ids:
            raise ValueError("duplicate capture identifier")
        origin = row.get("declared_source")
        if type(origin) is not str or origin not in SOURCE_LABELS[platform]:
            raise ValueError("invalid declared recording source")
        path = _capture_file(root, row.get("media_relpath"))
        if path in used_paths:
            raise ValueError("same private recording referenced twice")
        used_ids.add(capture_id)
        used_paths.add(path)
        observed[pair] = capture_id
        info = _digest_regular_file(path)
        key = scenario + ":" + platform
        if info is None:
            files[key] = {"file_present": False}
            warnings.append("recording_file_missing:" + key)
            continue
        n, digest = info
        total_bytes += n
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("total media byte budget exceeded")
        if digest in hashes:
            warnings.append("duplicate_recording_bytes:" + key)
        hashes[digest] = key
        if origin == "synthetic_fixture":
            warnings.append("synthetic_fixture_not_original_capture:" + key)
        files[key] = {
            "file_present": True,
            "byte_count": n,
            "sha256": digest,
            "declared_source": origin,
        }
    expected = [(scenario, platform) for scenario in SCENARIOS
                for platform in PLATFORMS]
    for scenario, platform in expected:
        if (scenario, platform) not in observed:
            warnings.append("capture_not_supplied:" + scenario + ":" + platform)
    blockers = sorted(set(warnings))
    return {
        "protocol_version": 1,
        "expected_capture_count": len(expected),
        "declared_capture_count": len(entries),
        "present_media_files": sum(x["file_present"] for x in files.values()),
        "total_recording_bytes_hashed": total_bytes,
        "media_by_scenario_and_platform": files,
        "structural_blockers": blockers,
        "all_ten_unique_files_present_without_blockers": not blockers,
        "source_video_decoding_performed": False,
        "video_frame_timestamps_verified": False,
        "controller_input_alignment_verified": False,
        "original_ios_recording_provenance_authenticated": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
        "interpretation": (
            "Private file existence and SHA-256 reproducibility only; "
            "declared capture origins are unauthenticated. Hashes do not "
            "establish authentic iOS gameplay, frame timestamps or physics."
        ),
    }


def main(argv=None) -> int:
    from .frame_alignment import _private_path
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    source = _private_path(args.manifest)
    target = _private_path(args.out)
    if source == target:
        raise ValueError("input and report cannot be the same private file")
    if source.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("capture manifest exceeds size bound")
    payload = json.loads(source.read_text(encoding="utf-8"))
    report = audit_capture_manifest(payload, Path.cwd() / "local_reports")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Private file inventory complete; no capture provenance proven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
