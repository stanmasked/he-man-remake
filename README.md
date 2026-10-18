# He-Man Switch Remake — research tools

Personal-use reimplementation research based on the user's locally obtained iOS copy of *He-Man: The Most Powerful Game in the Universe* (v2.0.0). This public repository contains **source-only, read-only format-analysis utilities**. It is **not a playable Nintendo Switch build**.

All original characters, game assets, sound, trademarks, and code remain the property of their respective rightsholders. **No IPA, APK, OBB, executable, textures, levels, music, extracted resources or private audit reports belong in this repository.** These files must be kept off GitHub entirely.

## Stage 001: level headers

A preliminary little-endian `.lvl` header reader. See `docs/format-lvl.md`.

## Stage 003: counted level objects

The new object reader decodes class/group/name/state, positional affine matrices, and typed properties. In local verification of iOS 2.0.0, it consumed all 3,943 counted objects from 39 files (including the bonus and credits maps). It leaves the trailing waypoint-like section and unknown per-object metadata undecoded. See `docs/format-objects.md`.

Run locally with Python 3.10+ (standard library only):

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m heman_tools.cli --ipa /secure/local/path/He-Man-v2.0.0.ipa --out local_reports/level_headers.json
PYTHONPATH=src python -m heman_tools.objects_cli --ipa /secure/local/path/He-Man-v2.0.0.ipa --level MULevel1-1.lvl --out local_reports/level1_objects.json
```

The original IPA is never uploaded by the CLIs. Local reports are excluded by `.gitignore`, and GitHub Actions uses synthetic tests only.

See `docs/roadmap.md` for the next tasks.
