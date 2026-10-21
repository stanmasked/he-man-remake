# Stage 110 — cross-check independently described Level 1-1 object roles

The Stage 109 private event-table audit ensured that the left gate maps to
`HM_TRIGGER`, while Skeletor Bio and Game Concept Art 09 map to two
different `HM_PICKUP` events. It could not distinguish **which of two
same-kind pickups is the actual original character biography**.

Stage 110 adds a second structural bridge, intentionally offline and
**never automatically enabling an original game map**.

## Local inputs

The CLI requires **four private JSON descriptions**, all stored under
the gitignored `local_reports/` directory:

1. `level11-private-readiness.json`, Stage103's redacted source
   candidate audit;
2. `level11-native-event-table.json`, Stage109's native event roles;
3. `level11-resource-object-claims.json`, claims from private
   resource/object investigation, channel `resource_candidate`;
4. `level11-observation-object-claims.json`, human annotations tied
   to separate observations, channel `observation_annotation`.

The latter two descriptions each list exactly three records, with:

- `role`: `left_gate`, `skeletor_bio`, or `concept_art_09`;
- `native_event_index`: the already checked C99 event index;
- `source_object_digest`: a 64-character lowercase SHA-256 *opaque
  object identifier* as assigned in local research notes;
- `artifact_file`: a relative path to a local supporting
  `.json`, `.png` or `.bin` file inside `local_reports/`;
- `artifact_sha256`: the actual SHA-256 of that local file;
- `original_contact_verified: false` — do not assert an unverified
  claim to be an authenticated original iOS contact.

Each claim bundle also requires `schema_version: 1`,
`level_key: "original-level-1-1"`, the channel label, and two explicit
`false` values for `original_ios_provenance_authenticated` and
`automatic_event_bindings_permitted`.

Both channels must agree on the same opaque source-object identifier
and the same native C99 event index for each role. The three source
objects must be different. All six evidence paths must resolve inside
the private directory without symlinks; contents are checked against
their SHA-256, with size bounds. The tool rejects sharing a file or
identical file contents across roles or channels. Wrong indices,
duplicated lore object identifiers, changed image/receipt bytes and
attempts to mark sources as authenticated fail the audit.

### Command (only when private reports and receipts already exist)

```sh
PYTHONPATH=src python -m heman_tools.level11_object_claim_reconciliation \
  --readiness local_reports/level11-private-readiness.json \
  --native local_reports/level11-native-event-table.json \
  --resource local_reports/level11-resource-object-claims.json \
  --observation local_reports/level11-observation-object-claims.json \
  --out local_reports/level11-object-correspondence.json
```

Example **fictional** resource claim row (not from the user's IPA):

```json
{
  "role": "skeletor_bio",
  "native_event_index": 1,
  "source_object_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "artifact_file": "fictional_receipts/resource_candidate-skeletor_bio.bin",
  "artifact_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "original_contact_verified": false
}
```

Those example digests are placeholders, and the command will reject
their use unless the actual local evidence file checksum matches.

## Output and crucial limits

The output contains only event counts, channel-consistency booleans and
fixed blocker codes. It **never includes source filenames, map pixels,
original images, object digests, local file paths or private event
indices**. It *always* reports:

- `original_ios_source_object_ownership_authenticated: false`
- `original_ios_contact_timing_authenticated: false`
- `original_geometry_verified: false`
- `automatic_collision_export_permitted: false`
- `switch_original_level_integration_permitted: false`

A matching SHA-256 verifies that a supplied file's current bytes match
a previously declared digest. **It cannot prove those bytes came from
the original game.** Two matching annotations can be copied from one
another, so comparing two channels does **not** establish independent
provenance or confirm iOS fidelity. No archived original IPA is
available in this execution environment; its contents have not been
re-extracted or authenticated at this stage. The original Level1-1
geometry, playable Switch scene and authentic gameplay timing remain
open in [Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).

Public GitHub Actions creates only six **fictional** tiny receipt files
for unit tests. No copyrighted game content, source-level coordinates,
private user data or new Switch NRO is added to the public repository.

### Test locally without an IPA

```sh
PYTHONPATH=src python -m unittest discover -s tests \
  -p test_level11_object_claim_reconciliation.py -v
```
