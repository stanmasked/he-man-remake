# Stage 075 — local collision-atlas alpha comparison

This source-only tool compares the *art alpha* of tile IDs used by a private
iOS map, between the \`screen-med\` and \`screen-xlarge\` resource packs.

## Private command

Install Pillow **locally** (GitHub CI does not need it). Keep the original IPA
outside the repository. From the project root:

\`\`\`sh
PYTHONPATH=src python -m heman_tools.alpha_pack_parity \
  --ipa /private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --out local_reports/level1-alpha-parity.json
\`\`\`

Only the Git-ignored \`local_reports/\` directory may contain the generated
JSON. The tool does not extract images, emit tile masks, retain decoded
artwork, upload files, or alter Switch gameplay. Its output comprises only
per-tile aggregate counts and ratios; it can still describe source-derived
details and should stay private.

## Comparison method

- Parse the original multi-layer \`.map\`, using only occupied cells of its
  uniquely named \`collision\` layer and the \`collision\` atlas.
- Require the source \`.map\` file to match **byte-for-byte** in both screen
  resource packs.
- Read the private RGBA PNG atlases directly from the existing IPA. Require
  \`screen-xlarge\` to have twice the dimensions of \`screen-med\`.
- Under the **unverified** assumption of equivalent row-major tile numbering,
  enlarge each 32×32 medium alpha tile to 64×64 with nearest-neighbor zoom,
  then compare binary alpha thresholds 64, 128, 192.
- Report intersection, union ratio, large-only and medium-only pixels.
  A double-empty mask has ratio 1 by convention.

For the user's privately held iOS v2.0.0 copy, the first map uses six tile
IDs (3–8). The threshold-128 match is excellent but not exact for five of the
six tile IDs. Tile ID 5 matches completely after 2× zoom.

**This does not verify game physics.** Opaque artwork is not automatically
a solid rectangle; image edges alone do not prove slopes, platforms, hazards,
contact damage, camera scale, original movement rules, or object ownership.
Automatic collision export remains disabled. The eight checks described in
\`docs/first-level-evidence-gate.md\` must be satisfied independently.

All CI tests use fabricated byte arrays and fake ZIP members, never original
art, map grids or the original IPA:

\`\`\`sh
PYTHONPATH=src python -m unittest discover -s tests -v
\`\`\`
