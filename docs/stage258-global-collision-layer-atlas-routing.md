# Stage258 — global collision-layer atlas routing census

## Purpose

Stage057/074 and Stage257 established first-level collision-layer occupancy and alpha-mask observations. Stage258 widens the audit to every parseable map resource in both screen packs. It counts which atlas names and tile IDs occur inside layers named collision, verifies exact source-map pair equality, and records whether each atlas name has a same-stem tileset resource.

The tool reads ZIP entries in memory and emits aggregate counts only. It does not export per-cell coordinates, map names, original bytes or images.

## Owner-private original-IPA findings

- 214 map files are present in each screen pack.
- 213 ordinary multilayer maps parse and are byte-identical across the two packs.
- One known special-format sky map is byte-different and excluded from the normal multilayer parser.
- 73 parseable maps contain a layer named collision, with 24,306 occupied cells.
- 23,618 occupied cells use the atlas named collision; the remaining 688 cells reference other atlas names.
- The cloud atlas is used in 11 maps; the special atlas alias is used in two maps.

The important conclusion is that a layer named collision does not imply that every occupied cell uses the collision atlas. The non-collision atlas references must be resolved before any native collision import.

## Unresolved alias: special

The special atlas alias has no same-stem special.tileset file. A similarly named texture candidate exists through another tileset, but the candidate does not agree across the two screen packs and is deliberately **not accepted as a mapping**. Its 197 occupied cells remain unresolved. Do not infer damage, solidity, sensors or other physics from the alias or texture name.

The complete owner-private atlas/tile frequencies, source-entry manifest and candidate comparison are preserved in the private Stage258 Drive handoff.

## Local command

Run from the repository root with Python 3.10+:

    PYTHONPATH=src python -m heman_tools.collision_layer_atlas_inventory --ipa /secure/private/He-Man-v2.0.0.ipa --out local_reports/collision-layer-atlas-routing.json

    PYTHONPATH=src python -m unittest discover -s tests -p test_collision_layer_atlas_inventory.py -v

Public CI uses fabricated multilayer maps only. The known special-format map is represented by a synthetic byte fixture; no original IPA is loaded by CI.

## Evidence boundary

The inventory proves only source-file parity and aggregate atlas routing. It does not establish collision response, solidity, slope behavior, one-way platforms, hazards, actor ownership, coordinate scale or original gameplay parity. All original collision semantics remain unverified, and native Switch collision import remains unauthorized until atlas aliases and runtime behavior are independently established.
