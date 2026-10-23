# Stage216 — private resource preservation and recovery

## Canonical source and destinations

The only canonical original is the owner-held [He-Man-v2.0.0.ipa](https://drive.google.com/file/d/1V84O73q9R-shnVmmwIjxzpqJezcyuSHG/view), whose Drive metadata reports **137,274,848 bytes**. Do not modify or re-upload a duplicate original.

The owner-only evidence archive is [He-Man Remake](https://drive.google.com/drive/folders/1xocndnS7B8itSFy_oK72Caw_9m41sVCB). Store the extracted bundle ZIPs in the [screen-med](https://drive.google.com/drive/folders/1Mrr8V3dYSlKb0FUnAeAGBOtekhZCrMgQ) and [screen-xlarge](https://drive.google.com/drive/folders/12Oam3ybDIgy5RhueQIxORPub9IR15P2V) folders under [08_Extracted_Assets](https://drive.google.com/drive/folders/14shQXkwD4IoZowBeOygz5SehwJQd8iU9). The detailed JSON manifest must go to the owner-only [00_Manifest_and_SHA256](https://drive.google.com/drive/folders/1EIR87LqihjvnSGEqqFi0-6SoenBtK6ba) folder. Store application resources outside the screen-specific subtrees in the [shared-assets](https://drive.google.com/drive/folders/1ZZH9s_P2jh3Gh85aQXVxQsl_F-jiTcJO) folder. These are selected by their original `Payload/MOTU.app/` paths, not inferred usage; this may include executable/support files. Files outside the app payload remain available in the unchanged original IPA.

## Local tool (no original resources in public CI)

Run from the repository root with the complete original IPA in an isolated local workspace. The `local_reports/` destination is Git-ignored. No credential or private archive belongs in the repository.

```sh
PYTHONPATH=src python -m heman_tools.private_asset_backup \
  --ipa /secure/He-Man-v2.0.0.ipa \
  --expected-source-bytes 137274848 \
  --canonical-source-url https://drive.google.com/file/d/1V84O73q9R-shnVmmwIjxzpqJezcyuSHG/view \
  --out-dir local_reports/stage216-backup
```

If a trusted baseline SHA-256 of the canonical IPA is available, add `--expected-source-sha256` with its 64-character lowercase hex digest. The tool always calculates and records the actual IPA SHA-256, requires the exact 137,274,848-byte length, checks source ZIP CRC for **all** members, and refuses incomplete/corrupt/unsafe or missing resolution packs. A truncated download of 109,707,264 bytes fails before extraction.

The tool emits **four private files**, retaining original paths relative to each selected app subtree:
- `heman-stage216-screen-med.zip`: complete `Payload/MOTU.app/screen-med/` subtree;
- `heman-stage216-screen-xlarge.zip`: complete `Payload/MOTU.app/screen-xlarge/` subtree;
- `heman-stage216-shared-assets.zip`: every remaining regular file within `Payload/MOTU.app/` (even if there are zero such files, the empty ZIP is retained as a completeness checkpoint);
- `heman-stage216-private-manifest.json`: source size/SHA-256 and CRC status, per-archive size/SHA-256/count, per-file path/size/SHA-256 and an app-wide file/byte total.

All regular files within `Payload/MOTU.app/` must belong to exactly one of these archives. This prevents a false "complete" backup that silently omits audio, metadata, or runtime support files outside the two screen trees.

Archives use deterministic order, stable ZIP timestamps and streaming copies. No overwrite of an existing checkpoint is allowed. Input ZIP paths are checked against traversal, duplicate paths, encryption, symlinks, and resource-size limits. Full source CRC and all ZIP/member hashes must pass before any archive is published locally. The private manifest contains original resource identifiers and **must never be committed or included in public CI**.

## Google Drive handoff, independent readback and recovery

Once the four local files exist:
1. Record **SHA-256 of the local manifest itself** in a separately trusted private stage handoff, before transferring it. This independent pin detects coordinated changes to the manifest and archive during storage/transfer.
2. Upload each of the three ZIPs and the JSON manifest to the corresponding **owner-only** Drive folders using a connector or authenticated private browser.
3. Verify each Drive file's ID, parent, full size, and name with metadata reads. Obtain a fresh copy of all three ZIPs and the manifest from Drive and verify the ZIP SHA-256 and every member SHA-256.
4. Run after downloading all ZIPs and the JSON sidecar into the same private folder:

```sh
PYTHONPATH=src python -m heman_tools.private_asset_backup \
  --verify-only --out-dir local_reports/stage216-restored-from-drive \
  --expected-manifest-sha256 SHA256_FROM_TRUSTED_PRIVATE_HANDOFF
```

5. `--verify-only` without `--expected-manifest-sha256` confirms **self-consistency only** and prints a warning; it does not establish the provenance of an untrusted downloaded manifest. For a restoration/verified-backup claim, the independent pin is mandatory.
6. Only **after** successful Drive readback should the project record a dated verification receipt containing Drive IDs, independently pinned manifest SHA-256, ZIP SHA-256 digests and sizes. The receipt remains private; it must not alter the original manifest values.
7. If Drive upload or readback fails, leave backup status at **pending** and keep the verified local copy. On a new session, start from the Drive archive + manifest and verify against the separately recorded SHA-256 before any extraction.

## Interrupted transfers: bounded parts and authenticated restoration

Because earlier transport returned a truncated 109,707,264-byte IPA against the canonical 137,274,848-byte Drive size, large derived ZIPs can optionally be **split into small checksummed parts** *after* the complete IPA has passed the source CRC gate. This does not repair or certify an incomplete IPA.

From the repository root, with the four locally verified backup files already under `local_reports/stage216-backup/`:

```sh
PYTHONPATH=src python -m heman_tools.private_archive_transfer stage \
  --backup-dir local_reports/stage216-backup \
  --transfer-dir local_reports/stage216-transfer-parts \
  --part-bytes 8388608
```

This creates 8 MiB-or-smaller numbered parts for each of the three ZIPs and the private manifest, plus a separate `heman-stage216-transfer-index.json`. The index records part sizes/SHA-256, complete file digests, and the original private manifest digest. **Store the transfer-index SHA-256 outside the transfer folder in a separate trusted private stage receipt before uploading.** The index is not public-safe; it reveals private backup metadata.

Upload parts and the private transfer index to the relevant owner-only Drive archives. It is acceptable to place the transfer index in `00_Manifest_and_SHA256`; the numbered parts may be stored in the appropriate resolution/shared-asset folders, with the manifest parts stored beside the index. For a partial failed upload, keep previously verified parts and transfer the missing parts individually. Do not mix parts from separate checkpoints.

After downloading all parts and index into one private `local_reports/stage216-downloaded-parts/` folder, restore with the **independently pinned** transfer-index hash:

```sh
PYTHONPATH=src python -m heman_tools.private_archive_transfer restore \
  --transfer-dir local_reports/stage216-downloaded-parts \
  --out-dir local_reports/stage216-restored-from-drive \
  --expected-index-sha256 SHA256_FROM_SEPARATELY_TRUSTED_RECEIPT
```

The tool validates the trusted index, each numbered chunk, every reassembled ZIP and the complete per-file backup manifest. It refuses overwrites and incomplete downloads. A self-consistent transfer is still not evidence of successful **Drive** backup unless its authenticated upload and independent re-download were observed.

## Stage216 evidence boundary

Source-controlled code and synthetic fixtures may run under GitHub Actions, but a public CI success does **not** mean the user's extracted game resources were uploaded, preserved, or reconstructed. Stage216 is complete only after the owner-private original has passed the source integrity gate and the backup archives and manifest have been uploaded to Drive and independently read back and verified.

**Status as of 2026-10-23:** script and synthetic tests are prepared; Drive destination folders exist. The user's original IPA was previously transferred incompletely in one session; original-resource backup upload and Drive readback are **not yet verified**. No claim of persisted extracted resources is made.
