# Stage 003: conservative object-record decoding

## Evidence from the private iOS 2.0.0 archive

The local source archive contains 39 paired level files in each of `screen-med` and `screen-xlarge`. The 39 same-named pairs are byte-identical. The new parser consumed the **counted object section** of all 39 level files:

- 3,943 objects across 39 files; the decoded count agrees with each header's count.
- 3,084 typed object properties: 2 booleans (tag 0), 1,312 signed 32-bit integers (tag 1), 1,081 IEEE float32 values (tag 2), 689 UTF-16LE strings (tag 3).
- Object entries provide class, group/alias, instance name, state, and a 3×3 float32 affine transform. Its final row is a plausible positional X/Y pair, but pixel-to-game coordinates remain unverified.
- There is **variable-length metadata after the state**: 3,868 records have 20 bytes before the transform marker, and 75 have 50 bytes. These bytes remain opaque rather than being guessed.
- A counted **trailing section** follows all objects in each file (110–1,768 bytes in the sample). It is *not parsed*. The leading unsigned integer is recorded only as a tentative item count.

The parser fails closed on unsupported types, truncated strings, non-finite float properties, missing matrix anchors, and implausible counts. It does not execute source scripts and does not decode collisions, tilemaps, waypoints, game physics, or visual assets.

## Local usage

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m heman_tools.objects_cli \
  --ipa /private/path/He-Man-v2.0.0.ipa \
  --level MULevel1-1.lvl \
  --out local_reports/level1_objects.json
```

**Data-handling rule:** `local_reports` is ignored by Git. Neither the original IPA nor extracted game assets nor derived per-level reports belong in this public repository.

The 22 host-side unit tests use *synthetic* fixture objects only. GitHub Actions can execute them without accessing the original game.
