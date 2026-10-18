# He-Man Switch Remake — research tools

Personal-use reimplementation research based on the user's locally obtained iOS copy of *He-Man: The Most Powerful Game in the Universe* (v2.0.0). This public repository contains **source-only, read-only format-analysis utilities**. It is **not a playable Nintendo Switch build**.

All original characters, game assets, sound, trademarks, and code remain the property of their respective rightsholders. **No IPA, APK, OBB, executable, textures, levels, music, extracted resources or private audit reports belong in this repository.** These files must be kept off GitHub entirely.

## Stage 001: level headers

The little-endian `.lvl` header reader is documented in `docs/format-lvl.md`.

## Stage 003: counted level objects

The object reader decodes class/group/name/state, positional affine matrices and typed properties. In local verification of iOS 2.0.0, it consumed all 3,943 counted objects from 39 files. Opaque object fields remain undecoded. See `docs/format-objects.md`.

## Stage 004: named point groups

A new read-only parser handles the trailing point groups, coordinate triples and local link indices. In private verification, all 39 files parsed exactly: 427 groups, 1,061 points and 134 index references. Game semantics of those links have *not* been established. See `docs/format-waypoints.md`.

Run locally with Python 3.10+ (standard library only):

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m heman_tools.cli --ipa /secure/local/path/He-Man-v2.0.0.ipa --out local_reports/level_headers.json
PYTHONPATH=src python -m heman_tools.objects_cli --ipa /secure/local/path/He-Man-v2.0.0.ipa --level MULevel1-1.lvl --out local_reports/level1_objects.json
PYTHONPATH=src python -m heman_tools.waypoints_cli --ipa /secure/local/path/He-Man-v2.0.0.ipa --level MULevel1-1.lvl --out local_reports/level1_points.json
```

The original IPA is never uploaded by any CLI. Local reports are excluded by `.gitignore`, and GitHub Actions uses synthetic tests only.

See `docs/roadmap.md` for the next tasks.

## Stages 005–006: schematics and geometric shape data

The asset-free SVG viewer renders decoded object and point coordinates with `PYTHONPATH=src python -m heman_tools.viewer_cli --ipa /private/He-Man-v2.0.0.ipa --out local_reports/level1.svg`. See `docs/level-viewer.md`.

The new `.shape` parser reads local-space polygons, circles and reference names. Run `PYTHONPATH=src python -m heman_tools.shape_scan --ipa /private/He-Man-v2.0.0.ipa --out local_reports/shapes.json`. See `docs/shape-format.md`. No collision map or playable Switch build has yet been completed.
