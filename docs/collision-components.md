# Stage 074 — private four-neighbor collision occupancy topology

Stage 073 established exact first-level references to a primary map and its
overlay. The next question is where candidate collision tiles form connected
groups, without assuming that every nonempty tile is solid terrain.

The new `collision_components` tool computes **four-connected occupancy**
(N, E, S, W), not gameplay collision shapes. For each connected component,
it reports a bounding rectangle in **grid cell coordinates**, occupied-cell
count, exposed cardinal grid-edge counts and candidate tile-ID frequencies.
Global summaries include group counts, singleton groups, adjacent occupied
cell pairs and the independently checked identity

`exposed_edges = 4 * occupied_cells - 2 * adjacent_occupied_pairs`.

The program reads the selected map independently from both private screen
packs, validates selected ZIP entries, and compares both exact source bytes
and the derived occupancy topology. A matching summary is not treated as
proof that source bytes match.

From a local source checkout:

```sh
PYTHONPATH=src python -m heman_tools.collision_components \
  --ipa /private/He-Man-v2.0.0.ipa \
  --map MUMap1-1.map \
  --out local_reports/level1-components.json

PYTHONPATH=src python -m unittest discover -s tests -v
```

This JSON contains **derived source level layout**, so the output path is
restricted to the Git-ignored `local_reports/` tree. Never commit the report,
original `.map` / IPA data, extracted collision textures or real tile grids.
GitHub Actions only tests fully fabricated grid fixtures.

## Evidence boundary

In the user's private iOS v2.0.0 source, the first candidate collision layer
contains 790 occupied cells spread among 20 four-connected components and
six observed tile IDs. This is a *grid topology observation*. The 754 cells
with tile ID 5 are **not** thereby established to be full solid blocks.
No object ownership, game-space coordinates, alpha-mask meaning, slope,
one-way platform, hazard, contact damage or player physics is inferred.

Any later use as native Switch collision surfaces still requires the eight
distinct evidence checks in `docs/first-level-evidence-gate.md`, including
independently observed original gameplay traces. No automatic collision-mask
export or Switch runtime modification is allowed by this stage.
