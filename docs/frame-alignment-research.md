# Stage 060 — private single-frame level/screenshot alignment hypothesis

Level-object coordinates decoded from the privately owned iOS IPA cannot
automatically be treated as screen pixels. A game's camera, resolution scale,
offset and coordinate-axis convention are not yet established. This tool
tests only an **axis-aligned, single-screenshot mathematical hypothesis**:

`screen_x = sx * level_x + tx` and `screen_y = sy * level_y + ty`.

It requires **four or more explicitly identified, independent point pairs**
with coordinates measured for the **same captured frame**. The fitting
procedure rejects duplicate identifiers, non-finite coordinates, degenerate
X/Y spreads, mixed frame IDs, substantial residuals, invalid input locations
and symlinked report roots. It does not silently fit arbitrary rotations or
shears, and reports both RMS and worst-case pixel error.

## Example input (entirely fabricated)

Create a private, ignored `local_reports/synthetic-anchors.json`:

```json
{
  "frame_id": "synthetic-frame-01",
  "anchors": [
    {"id": "a", "level_xy": [0, 0], "screen_xy": [20, 100]},
    {"id": "b", "level_xy": [10, 5], "screen_xy": [40, 85]},
    {"id": "c", "level_xy": [40, 25], "screen_xy": [100, 25]},
    {"id": "d", "level_xy": [90, 55], "screen_xy": [200, -65]}
  ]
}
```

From the repository root:

```sh
PYTHONPATH=src python -m heman_tools.frame_alignment \
  --anchors local_reports/synthetic-anchors.json \
  --out local_reports/synthetic-alignment.json \
  --max-residual-px 2
PYTHONPATH=src python -m unittest discover -s tests -v
```

The expected synthetic fit is `sx=2, tx=20, sy=-3, ty=100`.
The utility neither reads nor uploads the IPA or screenshots: it sees only
user-measured numeric coordinates in an ignored local JSON file. Its
report contains fitted parameters and errors, not the full input anchors.

## Evidence boundaries

A small fitting residual **does not validate point identity** or prove a
matching camera model. The fit applies only to one recorded frame and must
be checked independently on additional frames and objects. Do not feed
its parameters into actual game collision, player placement, hitboxes,
shape ownership or native level geometry without separate source-private
verification.

Fifteen entirely synthetic host tests cover matching, mismatches, under-
constrained anchors, rotated input, corrupted values and private JSON paths.
Original iOS game assets, screenshots, binaries and derived reports remain
outside the public repository and GitHub Actions.
