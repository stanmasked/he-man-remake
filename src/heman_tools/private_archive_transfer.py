"""Stage216: private, checksummed small-part transfer for original iOS backups.

This module does not download or upload assets by itself. It produces bounded
chunks to make private authenticated Drive transfer and readback resumable.
No private manifest or part belongs in a public Git repository or CI artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .private_asset_backup import (
    CHUNK_SIZE, MANIFEST_NAME, OUTPUT_FILENAMES, PACK_KEYS,
    PrivateBackupError, _require_private_directory, _sha256_file,
    _require_valid_digest, verify_private_backup,
)

TRANSFER_INDEX_NAME = "heman-stage216-transfer-index.json"
DEFAULT_PART_BYTES = 8 * 1024 * 1024
MAX_PART_BYTES = 32 * 1024 * 1024
MAX_PARTS_PER_FILE = 4096
FILES = (*OUTPUT_FILENAMES.values(), MANIFEST_NAME)


def _check_part_size(value: int) -> int:
    if type(value) is not int or not 256 <= value <= MAX_PART_BYTES:
        raise PrivateBackupError("Private transfer part size must be between 256 bytes and 32 MiB")
    return value


def _publish_temp_files(source_dir: Path, destination: Path, filenames: list[str]) -> None:
    if any((destination / name).exists() or (destination / name).is_symlink()
           for name in filenames):
        raise PrivateBackupError("Transfer target already exists; refusing to overwrite checkpoint")
    moved = []
    try:
        for name in filenames:
            src, dst = source_dir / name, destination / name
            os.rename(src, dst)
            moved.append(dst)
    except Exception:
        for item in moved:
            item.unlink(missing_ok=True)
        raise


def prepare_private_transfer(
    backup_directory: Path,
    transfer_directory: Path,
    *,
    part_bytes: int = DEFAULT_PART_BYTES,
) -> dict:
    """Verify a complete local backup then stage readback-verified small parts."""
    part_bytes = _check_part_size(part_bytes)
    if transfer_directory.exists() or transfer_directory.is_symlink():
        raise PrivateBackupError("Transfer destination already exists; no overwrite permitted")
    out = _require_private_directory(transfer_directory)
    verify_private_backup(backup_directory / MANIFEST_NAME, backup_directory)
    out.mkdir(parents=True, exist_ok=False)
    try:
        with tempfile.TemporaryDirectory(prefix=".stage216-chunk-", dir=out) as temporary:
            working = Path(temporary)
            files = []
            created = []
            for file_name in FILES:
                path = backup_directory / file_name
                if path.is_symlink() or not path.is_file():
                    raise PrivateBackupError("Backup file missing or symbolic link")
                original_sha256 = _sha256_file(path)
                original_bytes = path.stat().st_size
                parts = []
                with path.open("rb") as source:
                    index = 0
                    while data := source.read(part_bytes):
                        if index >= MAX_PARTS_PER_FILE:
                            raise PrivateBackupError("Private transfer exceeded per-file part limit")
                        part_name = file_name + f".part{index:05d}"
                        part_path = working / part_name
                        part_path.write_bytes(data)
                        part = {
                            "name": part_name,
                            "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                        }
                        parts.append(part)
                        created.append(part_name)
                        index += 1
                if not parts:
                    # The backup inputs are all nonempty ZIP or JSON files.
                    raise PrivateBackupError("Private transfer cannot stage an empty file")
                if sum(part["bytes"] for part in parts) != original_bytes:
                    raise PrivateBackupError("Private transfer source changed during staging")
                if _sha256_file(path) != original_sha256:
                    raise PrivateBackupError("Private transfer source SHA-256 changed during staging")
                files.append({
                    "name": file_name,
                    "bytes": original_bytes,
                    "sha256": original_sha256,
                    "parts": parts,
                })
            index_data = {
                "schema": "heman_private_transfer_v1",
                "part_bytes": part_bytes,
                "backup_manifest_sha256": _sha256_file(backup_directory / MANIFEST_NAME),
                "files": files,
                "verified_drive_readback": False,
            }
            index_path = working / TRANSFER_INDEX_NAME
            index_path.write_text(
                json.dumps(index_data, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            created.append(TRANSFER_INDEX_NAME)
            _publish_temp_files(working, out, created)
            return {
                "transfer_index_sha256": _sha256_file(out / TRANSFER_INDEX_NAME),
                "manifest_sha256": index_data["backup_manifest_sha256"],
                "part_count": len(created) - 1,
                "max_part_bytes": part_bytes,
                "status": "local parts ready; Drive upload and independent readback pending",
            }
    except Exception:
        # A failed staging operation is not a usable checkpoint.
        for entry in out.iterdir():
            if entry.is_file():
                entry.unlink()
        out.rmdir()
        raise


def restore_private_transfer(
    transfer_directory: Path,
    restored_directory: Path,
    *,
    expected_index_sha256: str,
) -> dict:
    """Require an independently pinned index SHA and verify every restored byte."""
    expected_index_sha256 = _require_valid_digest(expected_index_sha256)
    index_path = transfer_directory / TRANSFER_INDEX_NAME
    if index_path.is_symlink() or not index_path.is_file():
        raise PrivateBackupError("Private transfer index missing or linked")
    if index_path.stat().st_size > 8 * 1024 * 1024:
        raise PrivateBackupError("Private transfer index is oversized")
    if _sha256_file(index_path) != expected_index_sha256:
        raise PrivateBackupError("Transfer index differs from trusted private SHA-256")
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    if index_data.get("schema") != "heman_private_transfer_v1":
        raise PrivateBackupError("Invalid private transfer index schema")
    limit = _check_part_size(index_data.get("part_bytes"))
    manifest_sha = _require_valid_digest(index_data.get("backup_manifest_sha256"))
    records = index_data.get("files")
    if (not isinstance(records, list)
            or [f.get("name") for f in records if isinstance(f, dict)] != list(FILES)
            or len(records) != len(FILES)):
        raise PrivateBackupError("Private transfer file inventory is incomplete or altered")

    if restored_directory.exists() or restored_directory.is_symlink():
        raise PrivateBackupError("Restored directory already exists; refusing overwrite")
    out = _require_private_directory(restored_directory)
    out.mkdir(parents=True, exist_ok=False)
    try:
        with tempfile.TemporaryDirectory(prefix=".stage216-restore-", dir=out) as temporary:
            working = Path(temporary)
            used_parts = set()
            for record in records:
                part_records = record.get("parts")
                expected_size = record.get("bytes")
                if (type(expected_size) is not int or expected_size <= 0
                        or not isinstance(part_records, list)
                        or not 1 <= len(part_records) <= MAX_PARTS_PER_FILE):
                    raise PrivateBackupError("Malformed transfer part inventory")
                expected_file_sha = _require_valid_digest(record.get("sha256"))
                output = working / record["name"]
                file_digest = hashlib.sha256()
                total = 0
                with output.open("wb") as dest:
                    for index, part in enumerate(part_records):
                        expected_name = record["name"] + f".part{index:05d}"
                        if not isinstance(part, dict) or part.get("name") != expected_name:
                            raise PrivateBackupError("Transfer part names are not contiguous")
                        if expected_name in used_parts:
                            raise PrivateBackupError("Transfer part has been reused")
                        used_parts.add(expected_name)
                        part_file = transfer_directory / expected_name
                        part_size = part.get("bytes")
                        if (type(part_size) is not int or not 0 < part_size <= limit
                                or part_file.is_symlink() or not part_file.is_file()
                                or part_file.stat().st_size != part_size):
                            raise PrivateBackupError("Missing or invalid transfer part size")
                        expected_part_sha = _require_valid_digest(part.get("sha256"))
                        digest = hashlib.sha256()
                        with part_file.open("rb") as inp:
                            while data := inp.read(CHUNK_SIZE):
                                digest.update(data)
                                file_digest.update(data)
                                total += len(data)
                                if total > expected_size:
                                    raise PrivateBackupError("Transfer part assembly exceeded file size")
                                dest.write(data)
                        if digest.hexdigest() != expected_part_sha:
                            raise PrivateBackupError("Transfer part SHA-256 mismatch")
                if total != expected_size or file_digest.hexdigest() != expected_file_sha:
                    raise PrivateBackupError("Reassembled backup file size or SHA-256 mismatch")

            if _sha256_file(working / MANIFEST_NAME) != manifest_sha:
                raise PrivateBackupError("Restored manifest differs from independent private SHA-256")
            checked = verify_private_backup(
                working / MANIFEST_NAME, working, expected_manifest_sha256=manifest_sha,
            )
            _publish_temp_files(working, out, list(FILES))
            return {
                "status": "locally restored and verified (Drive provenance depends on private upload/readback)",
                "verified_archive_groups": len(checked),
                "verified_file_groups": len(records),
                "verified_part_count": len(used_parts),
                "manifest_sha256": manifest_sha,
            }
    except Exception:
        for entry in out.iterdir():
            if entry.is_file():
                entry.unlink()
        out.rmdir()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    make = modes.add_parser("stage", help="Prepare verified private transfer parts")
    make.add_argument("--backup-dir", required=True, type=Path)
    make.add_argument("--transfer-dir", required=True, type=Path)
    make.add_argument("--part-bytes", type=int, default=DEFAULT_PART_BYTES)
    restore = modes.add_parser("restore", help="Reconstruct and verify downloaded parts")
    restore.add_argument("--transfer-dir", required=True, type=Path)
    restore.add_argument("--out-dir", required=True, type=Path)
    restore.add_argument("--expected-index-sha256", required=True)
    args = parser.parse_args(argv)
    if args.mode == "stage":
        result = prepare_private_transfer(
            args.backup_dir, args.transfer_dir, part_bytes=args.part_bytes,
        )
    else:
        result = restore_private_transfer(
            args.transfer_dir, args.out_dir,
            expected_index_sha256=args.expected_index_sha256,
        )
    # Never print private hashes, filenames or source paths into shared logs.
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
