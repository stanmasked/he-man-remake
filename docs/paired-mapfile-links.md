# Stage 073: explicit first-level mapFileName references

The iOS level object metadata can contain a `LevelTileMap` object and a
`LevelTileMapOverlay` object. Their **typed string** property
`mapFileName` may name two different `.map` resources. Unlike a visual
filename guess, these are explicit references recorded within the `.lvl`
format, though the game runtime's interpretation is not independently proven.

Run a bounded, read-only cross-pack check on a privately held original IPA:

```sh
PYTHONPATH=src python -m heman_tools.paired_mapfile_links \
  --ipa /private/original.ipa --level MULevel1-1.lvl \
  --out local_reports/paired-mapfile.json
```

The new checker uses the preexisting `level_map_links.audit_local_ipa`
parser twice, once per screen variant. It requires exactly one typed
`mapFileName` candidate per object, the same object-index/class/resource
and parsed layer structure in both packs, and a unique layer literally named
`collision` for the primary map. In addition, it reuses the Stage 072
exact-byte checker for the level plus **both** selected map files; matching
layer counts with different underlying map data are rejected. It detects missing or ambiguous direct
references, unexpected collision layers on overlays, duplicate object
identities and contradictory source-physics claims.

The private JSON report can contain original resource names. Keep it and the
IPA in a protected, ignored local directory; do not publish either to
GitHub. The repository and GitHub CI contain only the Python checker and
fabricated test archives.

**Evidence limits:** A structurally consistent direct `mapFileName`
reference is better than a basename guess but is still *not* a captured
runtime binding, a solid-tile classification, a camera-coordinate model,
or original iOS gameplay evidence. As before:
`runtime_map_binding_verified = false`,
`collision_semantics_verified = false`, and
`automatic_collision_export_permitted = false`. The independent
eight-category manual review gate remains mandatory.
