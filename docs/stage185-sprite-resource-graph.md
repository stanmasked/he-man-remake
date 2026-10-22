# Stage185 — verified sprite-to-image reference graph

Stage185 adds a bounded, read-only private audit for the resource chain:

`SpriteSequence` symbol reference → `SpriteCutData` record → `TextureData` record → `ImageData` key → PNG member.

The audit was run locally against the owner-held iOS v2.0.0 IPA. Only aggregate counts and fixed capability flags are suitable for the public repository; original identifiers, paths, per-record values, offsets, bytes, image content and private reports remain local.

## Private aggregate result

Both source resolution packs independently passed strict record-boundary checks and agreed on the resource-reference structure.

| Check | Per-pack result |
|---|---:|
| Indexed sequence records parsed to exact EOF | 2,354 |
| Frames parsed | 7,889 |
| Symbol references examined | 14,971 |
| Symbol references matching the SpriteCut index | 13,432 |
| Symbol references without a SpriteCut index match | 1,539 |
| SpriteCut records | 1,156 |
| SpriteCut-to-TextureData links | 1,156 / 1,156 |
| Five-signed-int SpriteCut tuple entries | 2,334 |
| Cut handles matching zero-based tuple position | 2,334 / 2,334 |
| TextureData records linked to ImageData keys | 1,645 / 1,645 |
| ImageData path entries resolved | 1,647 / 1,647 |
| Unique PNG members validated | 1,644 |

The difference between 1,647 ImageData entries and 1,644 unique PNG members is explained by **three case-only path-alias groups** in the original index. Three path entries resolve only after case-insensitive comparison to an existing member. This matters for Nintendo Switch because archive paths are case-sensitive there, while the original iOS bundle resolves these case-only aliases. The port must preserve distinct resource keys while resolving these aliases deterministically; it must not blindly rename keys or invent missing files.

The 1,539 symbol references absent from the SpriteCut index are counted rather than treated as errors. Their role remains unknown and requires separate investigation.

## Native field-semantics correction

After the initial aggregate pass, a private read-only inspection of the original ARMv7 methods resolved the tuple semantics. `SpriteCut::fileIn` reads five signed integers; `SpriteRes::getCutForHandle` compares the first field to the requested handle; and `SpriteCut::buildTextCoord` uses the next four fields as x/y/width/height to calculate normalized texture coordinates. This corrects the earlier conservative statement that all four coordinate fields were opaque.

A raw PNG-header bounds comparison still finds 43 rectangle tuples outside the `screen-med` PNG dimensions and 80 outside the `screen-xlarge` PNG dimensions. This remains an unresolved reconciliation between serialized coordinates and runtime texture dimensions/padding, not permission to clip, discard, or rewrite geometry.

## Parser and safeguards

Added `src/heman_tools/sprite_cut_texture_image_graph.py`:

- Uses the previously validated sequence parser and bounded repository/WAD interval checks.
- Parses SpriteCut records as a texture key, count and exact sequence of five **signed** 32-bit fields per tuple.
- Original ARMv7 method inspection confirms the first field is a cut handle used by `SpriteRes::getCutForHandle`; in all 2,334 source tuples it equals the zero-based position.
- Original `SpriteCut::buildTextCoord` uses fields 2–5 as signed `x`, `y`, `width` and `height` when calculating normalized texture coordinates.
- Parses TextureData records as the indexed key, a 13-byte mixed-width scalar block, an empty auxiliary string, and the ImageData key. The scalar block is kept opaque because its individual fields' meanings are not needed to establish the graph.
- Strictly parses the separate ImageData repository envelope, rejects path traversal and validates PNG headers without extracting images.
- Resolves case-only aliases only when there is a unique matching archive member; ambiguous case-folded archive paths fail closed.
- Emits aggregate-only JSON under the ignored local reports directory. No original asset bytes or identifiers are uploaded.

Private local command:

```sh
PYTHONPATH=src python -m heman_tools.sprite_cut_texture_image_graph \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_cut_texture_image_graph.json
```

## Synthetic-only regression tests

`tests/test_sprite_cut_texture_image_graph.py` adds 15 fabricated-data tests for exact EOF, tuple counts and ordinals, missing graph links, unmatched symbols, path traversal, PNG validation, case-only aliases, ambiguous case-folded members, paired-pack consistency and output redaction.

These tests do not use the original IPA or original graphics. The private audit is not part of GitHub Actions.

## Remaining evidence gates

Stage185 establishes a source resource-reference chain, not the final renderer. Still unverified:

- reconciliation of some SpriteCut rectangles that exceed raw PNG IHDR dimensions with the original runtime's texture dimensions/padding; these values are not silently clipped;
- how SpriteCut handles are selected by each original Symbol during animation and how the resulting texture coordinates affect actual rendered frames;
- symbol transforms, anchors, blending and render order;
- the actor-state-to-sequence binding;
- authentic playback timing and visual parity in NeXium or on physical Switch hardware.

No gameplay NRO or original resource files were changed.
