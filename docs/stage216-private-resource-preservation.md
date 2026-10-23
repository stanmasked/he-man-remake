# Stage216 — private resource preservation and recovery

## Canonical source and destinations

The only canonical original is the owner-held [He-Man-v2.0.0.ipa](https://drive.google.com/file/d/1V84O73q9R-shnVmmwIjxzpqJezcyuSHG/view), whose Drive metadata reports **137,274,848 bytes**. Do not modify or re-upload a duplicate original.

The owner-only evidence archive is [He-Man Remake](https://drive.google.com/drive/folders/1xocndnS7B8itSFy_oK72Caw_9m41sVCB). Store the extracted bundle ZIPs in the [screen-med](https://drive.google.com/drive/folders/1Mrr8V3dYSlKb0FUnAeAGBOtekhZCrMgQ) and [screen-xlarge](https://drive.google.com/drive/folders/12Oam3ybDIgy5RhueQIxORPub9IR15P2V) folders under [08_Extracted_Assets](https://drive.google.com/drive/folders/14shQXkwD4IoZowBeOygz5SehwJQd8iU9). The detailed JSON manifest must go to the owner-only [00_Manifest_and_SHA256](https://drive.google.com/drive/folders/1EIR87LqihjvnSGEqqFi0-6SoenBtK6ba) folder. There is also a [shared-assets](https://drive.google.com/drive/folders/1ZZH9s_P2jh3Gh85aQXVxQsl_F-jiTcJO) folder for future proven shared assets; Stage216 does not invent a shared-resource classification.

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

The tool emits three private files, retaining all original nested paths *relative* to each screen pack:
- `heman-stage216-screen-med.zip`: full `Payload/MOTU.app/screen-med/` resource subtree;
- `heman-stage216-screen-xlarge.zip`: full `Payload/MOTU.app/screen-xlarge/` subtree;
- `heman-stage216-private-manifest.json`: source size/SHA-256 and CRC status, per-archive size/SHA-256/count, plus per-file path/size/SHA-256.

Archives use deterministic order, stable ZIP timestamps and streaming copies. No overwrite of an existing checkpoint is allowed. Input ZIP paths are checked against traversal, duplicate paths, encryption, symlinks, and resource-size limits. Full source CRC and all ZIP/member hashes must pass before any archive is published locally. The private manifest contains original resource identifiers and **must never be committed or included in public CI**.

## Google Drive handoff, independent readback and recovery

Once the three local files exist:
1. Upload each ZIP and the JSON manifest to the specific **owner-only** Drive folder named above, using a connector or an authenticated private browser session.
2. Verify each Drive file's ID, parent, full size, and name with metadata reads. Obtain a fresh copy of both ZIPs and the manifest from Drive and verify the ZIP SHA-256 and every member SHA-256.
3. Run after downloading both ZIPs and the JSON sidecar into the same private folder:

```sh
PYTHONPATH=src python -m heman_tools.private_asset_backup \
  --verify-only --out-dir local_reports/stage216-restored-from-drive
```

4. Only **after** successful Drive readback should the project record a dated verification receipt containing Drive IDs, verified SHA-256 digests, and the verified file sizes. Such a receipt remains private, alongside the manifest; it must not alter the original manifest values.
5. If Drive upload or readback fails, leave backup status at **pending** and keep the verified local copy. On a new session, start from the Drive archive + manifest and verify before doing any new extraction.

## Stage216 evidence boundary

Source-controlled code and synthetic fixtures may run under GitHub Actions, but a public CI success does **not** mean the user's extracted game resources were uploaded, preserved, or reconstructed. Stage216 is complete only after the owner-private original has passed the source integrity gate and the backup archives and manifest have been uploaded to Drive and independently read back and verified.

**Status as of 2026-10-23:** script and synthetic tests are prepared; Drive destination folders exist. The user's original IPA was previously transferred incompletely in one session; original-resource backup upload and Drive readback are **not yet verified**. No claim of persisted extracted resources is made.
