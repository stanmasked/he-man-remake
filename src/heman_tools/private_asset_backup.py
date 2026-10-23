"""Stage216: fail-closed, reproducible private backups of both iOS screen packs.

Only source code and synthetic tests belong in GitHub. Run this tool on the
owner's complete IPA in a private workspace; archives and detailed manifests
must remain in ignored local_reports/ and private Google Drive storage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, BadZipFile

from .physics_shape_census import PREFIX, SCREENS, MAX_MEMBERS

SOURCE_FILE_MAX = 1024 * 1024 * 1024
MEMBER_MAX = 256 * 1024 * 1024
EXTRACTED_TOTAL_MAX = 4 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
SHARED = "shared-assets"
PACK_KEYS = (*SCREENS, SHARED)
OUTPUT_FILENAMES = {
    SCREENS[0]: "heman-stage216-screen-med.zip",
    SCREENS[1]: "heman-stage216-screen-xlarge.zip",
    SHARED: "heman-stage216-shared-assets.zip",
}
MANIFEST_NAME = "heman-stage216-private-manifest.json"


class PrivateBackupError(ValueError):
    """Incomplete, corrupt, unsafe, or unverifiable owner-private backup."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while data := source.read(CHUNK_SIZE):
            digest.update(data)
    return digest.hexdigest()


def _safe_entry_name(name: str) -> bool:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        return False
    if any(ord(ch) < 32 for ch in name):
        return False
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and all(part not in ("", ".", "..") for part in name.split("/"))
        and len(name) <= 1000
    )


def _require_private_directory(directory: Path) -> Path:
    """Refuse paths outside the Git-ignored local_reports workspace."""
    root_candidate = Path.cwd() / "local_reports"
    if root_candidate.is_symlink():
        raise PrivateBackupError("local_reports may not be a symlink")
    root = root_candidate.resolve()
    destination = directory.resolve()
    if destination == root or not destination.is_relative_to(root):
        raise PrivateBackupError("Backup directory must be below local_reports/")
    parent = directory.absolute()
    while parent != root and parent.is_relative_to(root):
        if parent.is_symlink():
            raise PrivateBackupError("Backup path may not contain symlinks")
        parent = parent.parent
    return destination


def _selected_paths(archive: ZipFile) -> dict[str, list[tuple[object, str]]]:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        raise PrivateBackupError("Original IPA has too many ZIP members")
    names = set()
    casefold = set()
    selected: dict[str, list[tuple[object, str]]] = {key: [] for key in PACK_KEYS}
    total = 0
    for info in infos:
        name = info.filename
        if not _safe_entry_name(name.rstrip("/") if info.is_dir() else name):
            raise PrivateBackupError("Original IPA has unsafe ZIP member paths")
        if name in names or name.casefold() in casefold:
            raise PrivateBackupError("Original IPA has duplicate or case-conflicting member paths")
        names.add(name)
        casefold.add(name.casefold())
        if info.is_dir():
            continue
        if info.flag_bits & 1 or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
            raise PrivateBackupError("Encrypted or symlink IPA member is unsupported")
        if info.file_size < 0 or info.file_size > MEMBER_MAX:
            raise PrivateBackupError("IPA member size exceeds per-member safety limit")
        if info.compress_size < 0:
            raise PrivateBackupError("IPA member has an invalid compressed size")
        if not name.startswith(PREFIX):
            continue
        chosen = SHARED
        relative = name[len(PREFIX):]
        for screen in SCREENS:
            prefix = PREFIX + screen + "/"
            if name.startswith(prefix):
                chosen = screen
                relative = name[len(prefix):]
                break
        if not _safe_entry_name(relative):
            raise PrivateBackupError("Selected source member has an unsafe relative path")
        selected[chosen].append((info, relative))
        total += info.file_size
        if total > EXTRACTED_TOTAL_MAX:
            raise PrivateBackupError("Uncompressed application resources exceed safety limit")
    if any(not selected[screen] for screen in SCREENS):
        raise PrivateBackupError("Both original resolution packs must be present and nonempty")
    for key in PACK_KEYS:
        selected[key].sort(key=lambda item: item[1])
    return selected


def _copy_member(source: ZipFile, info, target: ZipFile, name: str) -> dict:
    digest = hashlib.sha256()
    size = 0
    target_info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    target_info.compress_type = ZIP_DEFLATED
    target_info.external_attr = 0o600 << 16
    target_info.create_system = 3
    with source.open(info, "r") as original, target.open(target_info, "w", force_zip64=True) as output:
        while data := original.read(CHUNK_SIZE):
            size += len(data)
            if size > MEMBER_MAX:
                raise PrivateBackupError("Source ZIP member exceeded declared safety limit")
            digest.update(data)
            output.write(data)
    if size != info.file_size:
        raise PrivateBackupError("Original ZIP member size mismatch")
    return {"path": name, "bytes": size, "sha256": digest.hexdigest()}


def _require_valid_digest(value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise PrivateBackupError("Expected SHA-256 must contain exactly 64 lowercase hex digits")
    return value


def build_private_backup(
    ipa: Path,
    destination: Path,
    *,
    expected_source_bytes: int,
    expected_source_sha256: str | None = None,
    canonical_source_url: str = "",
) -> dict:
    """Create two private ZIPs and one detail manifest only after full IPA checks.

    Refuses to overwrite any existing backup. Returns a private manifest; do not
    post its member paths, digests, or resource identifiers to public CI.
    """
    if type(expected_source_bytes) is not int or not 1 <= expected_source_bytes <= SOURCE_FILE_MAX:
        raise PrivateBackupError("Expected original IPA size must be a bounded positive integer")
    if expected_source_sha256 is not None:
        _require_valid_digest(expected_source_sha256)
    if not ipa.is_file() or ipa.is_symlink() or ipa.stat().st_size != expected_source_bytes:
        raise PrivateBackupError("Original IPA missing, symlinked, or does not match verified Drive byte size")
    source_sha = _sha256_file(ipa)
    if expected_source_sha256 is not None and source_sha != expected_source_sha256:
        raise PrivateBackupError("Original IPA SHA-256 differs from expected canonical source")
    if canonical_source_url and (
        not isinstance(canonical_source_url, str)
        or not canonical_source_url.startswith("https://drive.google.com/file/d/")
    ):
        raise PrivateBackupError("Canonical source URL must be an actual Drive file link")

    out = _require_private_directory(destination)
    out.mkdir(parents=True, exist_ok=True)
    final_paths = [out / name for name in (*OUTPUT_FILENAMES.values(), MANIFEST_NAME)]
    if any(path.exists() or path.is_symlink() for path in final_paths):
        raise PrivateBackupError("Backup target already exists; never overwrite a prior checkpoint")

    try:
        with ZipFile(ipa, "r") as source:
            selected = _selected_paths(source)
            # Every member (including non-screen resources) must pass CRC.
            if source.testzip() is not None:
                raise PrivateBackupError("Original IPA ZIP integrity test failed")
            with tempfile.TemporaryDirectory(prefix=".stage216-", dir=out) as temporary:
                working = Path(temporary)
                reports = {}
                for screen in PACK_KEYS:
                    archive_name = OUTPUT_FILENAMES[screen]
                    zip_path = working / archive_name
                    records = []
                    with ZipFile(zip_path, "w", allowZip64=True) as target:
                        for info, relative in selected[screen]:
                            records.append(_copy_member(source, info, target, relative))
                    reports[screen] = {
                        "filename": archive_name,
                        "archive_bytes": zip_path.stat().st_size,
                        "archive_sha256": _sha256_file(zip_path),
                        "file_count": len(records),
                        "uncompressed_bytes": sum(x["bytes"] for x in records),
                        "files": records,
                    }
                manifest = {
                    "schema": "heman_private_asset_backup_v1",
                    "stage": 216,
                    "source": {
                        "filename": ipa.name,
                        "canonical_drive_url": canonical_source_url,
                        "bytes": ipa.stat().st_size,
                        "sha256": source_sha,
                        "zip_crc_verified": True,
                    },
                    "tool": "heman_tools.private_asset_backup v1 (Python stdlib, ZIP_DEFLATED)",
                    "screen_packs": {screen: reports[screen] for screen in SCREENS},
                    "shared_resources": reports[SHARED],
                    "application_file_count": sum(reports[key]["file_count"] for key in PACK_KEYS),
                    "application_uncompressed_bytes": sum(reports[key]["uncompressed_bytes"] for key in PACK_KEYS),
                    "backed_up_to_drive": False,
                    "drive_readback_verified": False,
                    "original_runtime_pixel_parity_verified": False,
                }
                manifest_path = working / MANIFEST_NAME
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                verify_private_backup(manifest_path, working)
                published = []
                try:
                    for file_name in (*OUTPUT_FILENAMES.values(), MANIFEST_NAME):
                        src, dst = working / file_name, out / file_name
                        if dst.exists():
                            raise PrivateBackupError("Another backup populated the output directory")
                        os.rename(src, dst)
                        published.append(dst)
                except Exception:
                    for item in published:
                        item.unlink(missing_ok=True)
                    raise
                return manifest
    except (BadZipFile, EOFError, OSError) as exc:
        raise PrivateBackupError("IPA or private archive failed structural validation") from exc


def verify_private_backup(manifest_path: Path, directory: Path) -> dict:
    """Verify all output archive digests and per-member content against a manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "heman_private_asset_backup_v1":
        raise PrivateBackupError("Unrecognized backup manifest schema")
    packs = manifest.get("screen_packs")
    if not isinstance(packs, dict) or set(packs) != set(SCREENS):
        raise PrivateBackupError("Manifest must describe both resolution packs")
    shared = manifest.get("shared_resources")
    if not isinstance(shared, dict):
        raise PrivateBackupError("Manifest must describe application-level shared assets")
    records = {**packs, SHARED: shared}
    summary = {}
    for screen in PACK_KEYS:
        record = records[screen]
        filename = OUTPUT_FILENAMES[screen]
        if record.get("filename") != filename:
            raise PrivateBackupError("Unexpected ZIP name in backup manifest")
        zip_path = directory / filename
        if zip_path.is_symlink() or not zip_path.is_file():
            raise PrivateBackupError("Missing or linked private archive")
        if (zip_path.stat().st_size != record.get("archive_bytes")
                or _sha256_file(zip_path) != _require_valid_digest(record.get("archive_sha256"))):
            raise PrivateBackupError("Backup ZIP byte size or SHA-256 mismatch")
        files = record.get("files")
        if not isinstance(files, list) or (not files and screen != SHARED) or len(files) > MAX_MEMBERS:
            raise PrivateBackupError("Manifest must have a bounded per-file inventory")
        expected = {}
        for entry in files:
            name = entry.get("path")
            if not _safe_entry_name(name) or name in expected:
                raise PrivateBackupError("Unsafe or duplicate manifest member path")
            expected[name] = entry
        with ZipFile(zip_path, "r") as archive:
            infos = archive.infolist()
            if len(infos) != len(files) or {x.filename for x in infos} != set(expected):
                raise PrivateBackupError("Archive content differs from manifest inventory")
            for info in infos:
                if info.is_dir() or info.flag_bits & 1 or info.file_size != expected[info.filename].get("bytes"):
                    raise PrivateBackupError("Archive member size or type mismatch")
                digest = hashlib.sha256()
                with archive.open(info, "r") as stream:
                    while data := stream.read(CHUNK_SIZE):
                        digest.update(data)
                if digest.hexdigest() != _require_valid_digest(expected[info.filename].get("sha256")):
                    raise PrivateBackupError("Extracted member SHA-256 mismatch")
        if len(files) != record.get("file_count") or sum(x["bytes"] for x in files) != record.get("uncompressed_bytes"):
            raise PrivateBackupError("Manifest aggregate counts do not match")
        summary[screen] = {"files": len(files), "zip_bytes": zip_path.stat().st_size, "verified": True}
    if (sum(v["files"] for v in summary.values()) != manifest.get("application_file_count")
            or sum(records[key]["uncompressed_bytes"] for key in PACK_KEYS)
                != manifest.get("application_uncompressed_bytes")):
        raise PrivateBackupError("Application-wide archive coverage counts do not match")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--expected-source-bytes", type=int)
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--canonical-source-url", default="")
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify archives downloaded from Drive against the private manifest")
    args = parser.parse_args(argv)
    if args.verify_only:
        if args.ipa is not None or args.expected_source_bytes is not None:
            parser.error("--verify-only must not be combined with source extraction options")
        checked = verify_private_backup(args.out_dir / MANIFEST_NAME, args.out_dir)
        print("Stage216 three-pack private archive SHA-256 and contents verified: "
              + ", ".join(f"{screen}={checked[screen]['files']} files" for screen in PACK_KEYS))
        return 0
    if args.ipa is None or args.expected_source_bytes is None:
        parser.error("backup requires --ipa and --expected-source-bytes")
    manifest = build_private_backup(
        args.ipa, args.out_dir,
        expected_source_bytes=args.expected_source_bytes,
        expected_source_sha256=args.expected_source_sha256,
        canonical_source_url=args.canonical_source_url,
    )
    print(
        "Stage216 private archive verified locally: "
        + ", ".join(
            f"{screen}={manifest['screen_packs'][screen]['file_count']} members"
            for screen in PACK_KEYS
        )
        + "; Google Drive upload and readback still pending."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
