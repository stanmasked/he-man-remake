# Stage142 — evidence census for unresolved iOS physics bytes

This continues Stage141's bounded parsing of the original iOS v2.0.0
physical-structure record envelopes. The original archive was examined
read-only outside GitHub. Public source contains no original physics bytes,
geometry, labels, coordinates or shapes.

## Owner-private original observations

| Aggregate property | Observation |
|---|---:|
| Paired physics files | 81 |
| Repeated records with an opaque 50-byte field | 187 |
| Distinct 50-byte blocks | 139 |
| Records with an entirely zero 50-byte block | 0 |
| Byte positions changing across 187 blocks | 38 of 50 |
| Byte positions constant across all blocks | 12 of 50 |
| Files with a nonzero trailing group count | 13 |
| Sum of declared trailing group counts | 44 |
| Total bytes in the 13 still-unknown tails | 1,691 |
| Minimum / maximum nonempty tail sizes | 40 / 225 bytes |
| Tails admitting a candidate leading u16-length UTF-16 string | 13 / 13 |
| Candidate leading empty strings | 6 |
| Candidate leading nonempty strings | 7 |

The fixed 50-byte section is not invariant padding, but variability
alone cannot establish which positions correspond to flags,
transforms, integers, floats or collision materials. No individual
source offsets or values are released.

All 13 unknown trailers begin with bytes that could represent one
syntactically valid u16-length-prefixed UTF-16 string. That is not a
complete trailer record parser. There is no verified boundary,
field size or semantic type for the 44 *declared* group items.
They are NOT confirmed physical joints or constraints.

## Privacy-safe local-only probe

The source module src/heman_tools/physics_opaque_probe.py reuses
Stage141's validated record envelope and Stage140's size-bounded,
paired-resource reader. It rewalks the private records, counts the
50-byte patterns only in process memory, and tests whether each unknown
trailer starts with a plausible length-prefixed UTF-16 token.

Run ONLY on a private owner-controlled original IPA:

    PYTHONPATH=src python -m heman_tools.physics_opaque_probe \
      --ipa /secure/private/He-Man-v2.0.0.ipa \
      --out local_reports/physics_opaque_evidence.json

The report contains aggregate counters and permanent unverified flags
only. It has no original names, byte positions, raw values, hashes,
hitboxes, vertices, asset paths or original level geometry. Keep all
reports in the existing ignored local_reports/ directory, not GitHub.

CI uses 15 completely artificial scenarios: changing/identical opaque
blocks, valid/invalid candidate first labels, zero tails, truncated
records, malformed counts, paired resource differences, ZIP duplicate
and symlink rejection, redaction and size-budget checks.

## Unverified / remaining work

- No full byte-for-byte parser for the 13 optional trailer sections.
- No identification of fields within the 50-byte parameter block.
- No validated iOS physics joints, sensors, materials or per-object
  collision-shape ownership.
- No proven coordinate transform, runtime physics or original
  gameplay trace.
- No authorization to import proprietary iOS collision geometry
  into the independently authored Switch NRO.

Next step: falsify candidate repeated-tail layouts on synthetic
records, then privately check whether a candidate consumes all 13
original trailer payloads exactly. Until the format is established,
keep every trailer byte opaque and do not assign physics semantics.
