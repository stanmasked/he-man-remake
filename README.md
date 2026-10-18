# He-Man Switch Remake — research tools

Personal-use reimplementation research based on the user's locally obtained iOS copy of *He-Man: The Most Powerful Game in the Universe* (v2.0.0). This public repository contains **source-only, read-only format-analysis utilities**. It is **not a playable Nintendo Switch build**.

All original characters, game assets, sound, trademarks, and code remain the property of their respective rightsholders. **No IPA, APK, OBB, executable, textures, levels, music, extracted resources or private audit reports belong in this repository.** These files must be kept off GitHub entirely.

## Stage 001: conservative `.lvl` header reader

The reader recognizes the preliminary layout observed in a private sample of 39 `.lvl` files: little-endian version, six float32 values, a length-prefixed UTF-16LE filename, a probable serialized-record count, and an optional first-record label. It does *not* decode entity bodies, collisions, scripts, or texture references.

Run locally with Python 3.10+ (standard library only):

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m heman_tools.cli --ipa /secure/local/path/He-Man-v2.0.0.ipa --out local_reports/level_headers.json
```

The original IPA is never uploaded by the CLI, and local reports are excluded by `.gitignore`.

See `docs/format-lvl.md` and `docs/roadmap.md` for limitations and development milestones.
