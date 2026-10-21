# Stage 109 — private Level 1-1 event-role preflight

Stages 102–108 built and tested the opt-in C99 machinery for Wall
Crusher, two lore rewards, native physics-bound contact checks, fresh
attack button edges, world/binding identity, and experimental player
saves. **Those mechanics still have no authenticated original iOS
Level 1-1 coordinates or event ownership.**

Stage 103 already checked candidate `.lvl`→`.map`/shape/collision
reports offline. This Stage 109 auditor closes a different structural
gap: the exact **three logical roles** in a proposed native event table
must refer to unique, correct native C99 event kinds:

| Role | Required native event kind |
| --- | --- |
| `left_gate` | `HM_TRIGGER` |
| `skeletor_bio` | `HM_PICKUP` |
| `concept_art_09` | `HM_PICKUP` |

It checks a full contiguous, ordered event table of between three
and 32 native event descriptors; exactly one binding per role;
no shared indices, role-kind mismatches, unknown extra fields,
import authorization, or assertions of independently verified
source contact/geometry. The Stage 103 structural readiness report
is required and must retain all six negative original-source
authentication flags.

The output is a **redacted research diagnostic only**: it exposes no
source filenames, original coordinates, event indices, media assets,
tile arrays or private resource hashes. The result **always** says
`switch_original_level_integration_permitted: false`.

## Local-only example using fictional descriptors

The tool is designed for source-private offline workflows. Two files
must already exist inside the repo's ignored `local_reports/`:

- `local_reports/level11-private-readiness.json`, produced by
  `heman_tools.level11_private_readiness` in Stage 103;
- `local_reports/level11-native-event-table.json`, locally prepared
  from a native scene being reviewed. This second file has a strict
  schema and **must not contain source geometry**.

A minimal **fictional** event table for understanding the schema
(not original iOS positions or object order):

```json
{
  "schema_version": 1,
  "level_key": "original-level-1-1",
  "native_world_event_count": 3,
  "events": [
    {"index": 0, "kind": "HM_TRIGGER"},
    {"index": 1, "kind": "HM_PICKUP"},
    {"index": 2, "kind": "HM_PICKUP"}
  ],
  "roles": [
    {"role": "left_gate", "event_index": 0, "event_kind": "HM_TRIGGER",
     "source_contact_verified": false},
    {"role": "skeletor_bio", "event_index": 1, "event_kind": "HM_PICKUP",
     "source_contact_verified": false},
    {"role": "concept_art_09", "event_index": 2, "event_kind": "HM_PICKUP",
     "source_contact_verified": false}
  ],
  "world_coordinate_transform_verified": false,
  "original_collision_semantics_verified": false,
  "ios_capture_contact_timing_verified": false,
  "automatic_gameplay_enable_permitted": false
}
```

Run only after preparing the private Stage 103 report and private
native role table; do **not** upload either report to GitHub:

```sh
PYTHONPATH=src python -m heman_tools.level11_event_binding_preflight \
  --readiness local_reports/level11-private-readiness.json \
  --events local_reports/level11-native-event-table.json \
  --out local_reports/level11-event-binding-audit.json
```

The CLI enforces that **all inputs and outputs** remain under the
ignored `local_reports/` directory and prevents file reuse;
it rejects source-bearing extra keys, malformed event ordering,
misassigned roles, and fabricated source authenticity flags.
The public GitHub CI tests only fictional descriptors.

### Exact limitations

This audit checks **structural consistency**, not whether the actual
original Level 1-1 has those coordinates, event numbers, camera
transform, collision ownership, or saving rules. A successfully
formed fictional event table can pass its type checks while
containing **no original iOS data whatsoever**. It therefore never
generates C99 source bindings, authorizes original collision export
or marks the real level as playable. The user-owned original
`He-Man-v2.0.0.ipa` was unavailable in the current active runtime;
nothing was secretly re-extracted, uploaded or verified from it.

Next source-authenticity requirements are still tracked in
[Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).
No existing Switch NRO/NeXium guest path is changed.
