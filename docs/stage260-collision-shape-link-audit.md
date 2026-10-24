# Stage260 — collision tile to Shape2D resource links

## Purpose

Stage257/259 established that atlas alpha masks can be measured reproducibly, but alpha coverage is not the engine's collision-data contract. Stage260 follows the actual serialized collision tileset records and resolves non-empty per-tile shape references to the paired `.shape` resources.

The owner-private static disassembly of the original ARMv7 executable independently established this path:

1. The tileset loader reads each tile record.
2. The tile record reader forwards a non-empty shape-reference string to the shape-resource loader.
3. Collision initialization checks whether a tile has a loaded shape.
4. A referenced shape takes the vertex-based polygon-generation path; an empty reference takes a separate tile-metadata fallback path.
5. The explicit shape path reads the polygon's vertex count and vertices before creating the Box2D polygon shape.

The raw disassembly, offsets and source executable remain private. The public tool is a bounded resource-link audit; it does not run the disassembler and does not claim to verify gameplay behavior by itself.

## Owner-private original source result (aggregate only)

The first-level collision layer has 790 occupied cells across six used tile IDs. Three of the six used tile IDs contain non-empty shape references, and all three resolve to exactly one `.shape` resource in both resolution packs. The other three have empty shape references and follow the separate fallback path identified in the executable.

All three referenced resources decode as polygons with vertex counts **3, 4 and 4** (11 vertices total), and each referenced resource is byte-identical between the medium and xlarge packs. The source maps are byte-identical, the tileset rectangles follow a uniform 2× scale, and the per-tile collision metadata and shape-reference strings agree across packs.

Only aggregate counts are published. Per-tile names, metadata, resource hashes and local geometry summaries remain in the owner-only Drive handoff. No original executable, map, tileset or shape bytes are committed.

## Local command

Run from the repository root with Python 3.10+:

```sh
PYTHONPATH=src python -m heman_tools.collision_shape_link_audit \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --out local_reports/level1-collision-shape-links.json

PYTHONPATH=src python -m unittest discover -s tests -p 'test_collision_shape_link_audit.py' -v
```

The tool parses the runtime tileset record layout, checks the collision layer's used tile IDs, resolves exact shape stems in both screen packs, compares metadata and rectangles, and writes detailed output only beneath the Git-ignored `local_reports/` directory. It reads the original archive in memory and never extracts source entries.

## Interpretation boundary

This stage confirms the serialized tile-to-shape resource link and the existence of the separate fallback path. It does not infer the meaning of opaque collision categories or bit masks, prove one-way/hazard/destructible behavior, establish world transforms, or compare against an authoritative original-device gameplay trace.

Do not import the original shapes or fallback metadata into the Switch gameplay engine until their world-space transforms and runtime behavior are independently validated.

## Public test boundary

GitHub Actions uses fully synthetic maps, runtime-format tilesets and polygon resources. It never loads the original IPA or stores source-derived per-tile details. The summary keeps original gameplay parity and native Switch collision import explicitly unverified.
