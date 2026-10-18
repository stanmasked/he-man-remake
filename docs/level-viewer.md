# Stage 005 — asset-free level schematic viewer

This project now renders 2D point diagrams directly from validated, **locally read** level data.

## What the renderer displays

- Every decoded object as a color-coded dot, with optional name/coordinates in its SVG hover tooltip.
- Camera, checkpoint and door labels, with basic overlap filtering.
- Every decoded named 3D point as a diamond, projected to its recorded X/Y coordinates.
- Links among points in the *same named group* as dashed segments, keeping duplicates in memory.
- Horizontal/vertical coordinate rulers, configurable horizontal zoom, and a category legend.

**Not yet implemented:** level art, collision meshes, tile sizes, animation playback, enemy AI, player movement, faithful camera simulation, or a Nintendo Switch build.

This is a *schematic visualization only*. The X and Y axes are scaled **independently**, so apparent slope, distance, platform extent and jump length are not physically meaningful. Named groups and connections are raw serialized relationships, not established gameplay movement paths.

## Private local usage

Using Python 3.10+ and the user's locally acquired iOS 2.0.0 IPA:

```sh
PYTHONPATH=src python -m heman_tools.viewer_cli \
  --ipa /private/He-Man-v2.0.0.ipa \
  --level MULevel1-1.lvl \
  --out local_reports/level1-overview.svg

PYTHONPATH=src python -m heman_tools.viewer_cli \
  --ipa /private/He-Man-v2.0.0.ipa \
  --level MULevel1-1.lvl \
  --min-x 0 --max-x 2200 \
  --out local_reports/level1-start.svg

PYTHONPATH=src python -m unittest discover -s tests -v
```

Open resulting SVG files with a browser or an SVG viewer. Hover over dots/diamonds for original identifiers. Generated SVGs and reports are deliberately placed under `local_reports/` which is ignored by Git.

## Validation

- 11 additional synthetic tests for XML parseability, escaping special characters, bounds, zoom, category rendering, lack of embedded JavaScript/images and local archive handling.
- Local suite after Stage 005: **46/46 passed**.
- Local source preview: `MULevel1-1.lvl` contains 159 counted objects, 10 named groups, 30 points and 3 indexed links.
- No original copyrighted textures or level bodies are committed to GitHub.
