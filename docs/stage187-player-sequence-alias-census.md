# Stage187 — directional sequence-alias census

Stage187 follows Stage186's component-level selection contract by auditing the serialized alias-to-sequence table in the owner-held iOS v2.0.0 GO data. The original IPA is inspected locally; no original labels, sequence keys, byte offsets, executable bytes, images, or per-entry records are committed.

## Private source audit

Two directional-sprite data windows were selected from the private GO data layout. Both iOS resolution packs have byte-identical `go/default` data and byte-identical `SpriteSeqData.repo` indexes.

| Aggregate check | First component window | Second component window |
|---|---:|---:|
| Exact sequence-resource references | 184 | 188 |
| Distinct sequence keys referenced | 152 | 132 |
| Alias entries with exactly one east/west resource pair | 79 | 79 |
| Distinct aliases with a unique pair | 77 | 79 |
| Alias groups requiring further parsing | 6 | 8 |
| References inside ambiguous groups | 26 | 30 |
| Unassigned sequence references | 0 | 0 |
| Resource-like tokens absent from the sequence index | 0 | 0 |

The parser does not force ambiguous groups into pairs. In particular, some aliases precede multiple east/west pairs, so treating the next pair as the only mapping would silently discard original configuration.

### Cross-window comparison

- 75 distinct aliases with a uniquely paired entry appear in both windows.
- 73 of those aliases have exactly one pair in each window; two are excluded because the first window contains duplicate pair entries for them.
- Of the 73 comparable aliases, 58 point to the same resource pair and 15 point to different pairs.
- All 184 and 188 exact resource references resolve to keys in the original SpriteSequence repository. No key or alias is included in this report.

### Executable-string cross-check

Every distinct alias with a confirmed directional pair also occurs as an exact standalone ASCII string token in the original executable image: **77/77** aliases from the first window and **79/79** from the second, including all **75/75** shared aliases. This makes it unlikely that the alias labels are artifacts of the GO-data scanner. The remaining missing link is semantic: the static handle value used by each C++ state constructor has not yet been tied to its corresponding alias at runtime.

This supports a data-driven alias-to-directional-sequence table and gives a concrete next target for runtime tracing. It does **not** yet prove which C++ player-state handle emits each alias, nor whether the serialized message dispatch reaches the expected component at runtime.

## Implementation and safeguards

Added `src/heman_tools/player_sequence_alias_census.py`:

- Uses exact length-prefixed UTF-16LE repository-key matching.
- Accepts two bounded component windows discovered during owner-private inspection.
- Counts only a group with exactly two references, one `.e` and one `.w`, as a confirmed directional pair.
- Keeps multi-pair groups ambiguous and counts their references without inventing a mapping.
- Requires both resolution packs' GO data and SpriteSequence indexes to be byte-identical.
- Emits aggregate-only JSON through the local ignored-report path. The private IPA audit is not part of public CI.

The new `tests/test_player_sequence_alias_census.py` uses fabricated aliases and resource keys only. It covers paired and changed mappings, ambiguous groups, unassigned references, missing repository keys, duplicate aliases, invalid windows, duplicate keys and report redaction.

## Next step

Trace the state-specific code and message payload that chooses these serialized aliases. Keep the two unresolved layers separate: alias → directional sequence is now audited as data; gameplay state handle → alias/message still needs direct evidence. Then reconcile SpriteCut rectangles beyond raw PNG IHDR bounds and verify a real frame in NeXium.
