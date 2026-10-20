# Stage 062 — held-out coordinate calibration check

A fit with low training residual can still be a coincidence. This private-only
tool tests a previously defined axis-aligned one-frame mapping against
**independently reserved landmarks**. It requires at least 4 training anchors
for the existing `frame_alignment.fit_single_frame` model and 2–32 additional
validation anchors, all from the **same recorded frame**.

Training landmarks fit `x'=sx*x+tx`, `y'=sy*y+ty`. Held-out landmarks
**do not participate in that fit**: the tool measures their errors only
afterwards, rejecting a fit that looks accurate in training but predicts
other measured landmarks badly.

To avoid accidental leakage, validation landmarks require distinct IDs
and distinct source positions from both training and each other. Malformed
coordinates, mixed frames, excessive residuals and private path escapes
fail closed. Results contain aggregate errors, fitted parameters and
limitations, not the source landmarks.

## Private-only command

Create a JSON file in the ignored `local_reports/` directory:

```json
{
  "frame_id":"synthetic-frame-12",
  "anchors":[
    {"id":"train-a","level_xy":[0,0],"screen_xy":[20,100]},
    {"id":"train-b","level_xy":[10,5],"screen_xy":[40,85]},
    {"id":"train-c","level_xy":[40,25],"screen_xy":[100,25]},
    {"id":"train-d","level_xy":[90,55],"screen_xy":[200,-65]}
  ],
  "holdout_anchors":[
    {"id":"test-a","level_xy":[30,70],"screen_xy":[80,-110]},
    {"id":"test-b","level_xy":[75,15],"screen_xy":[170,55]}
  ]
}
```

```sh
PYTHONPATH=src python -m heman_tools.heldout_alignment \
  --anchors local_reports/synthetic-training-holdout.json \
  --out local_reports/synthetic-heldout-results.json \
  --max-fit-residual-px 2 \
  --max-holdout-residual-px 2

PYTHONPATH=src python -m unittest discover -s tests -v
```

The example is deliberately fabricated. The tool does **not** read an IPA,
original frames, pixel data or extracted maps and cannot verify the identity
of manually selected landmarks. Even a passed holdout check does not
prove the iOS camera model, physical scale, shape ownership, collision
or cross-frame correctness.

18 synthetic-only tests cover a correct fit, bad held-out data despite a
perfect training fit, coordinate/ID leakage, differing frames, bad
tolerances, malformed inputs and restricted private JSON output. Keep all
commercial source resources and real measurement reports outside GitHub.
