# Stage 061 — stationary-landmark cross-frame consistency

A successful single-frame coordinate fit can be coincidental. This evidence-only
tool compares **two to 32** separate captures, using the single-frame tool in
Stage 060, to test whether an *axis-aligned constant scale* can plausibly explain
the same set of manually identified stationary landmarks.

## Preconditions and method

All frames must contain the **same four or more physical landmarks**, with
identical IDs and decoded `level_xy` coordinates. Each frame receives its
own `screen_xy` measurements and unique `frame_id`. The model fits
`screen_x=sx*level_x+tx` and `screen_y=sy*level_y+ty` independently to
each frame, allows independent `tx,ty` as the camera may move, and requires
the same scales (within a configurable relative tolerance).

Fail-closed checks reject mixed identities, different level coordinates,
duplicate frames, inappropriate anchor residuals, rotated/sheared mappings,
scale drift/zoom or axis flips. A successful fit is still **not** evidence
of correct manual landmark identities, original engine camera rules,
perspective, parallax, original physical units or collision geometry.

## Entirely fabricated example

Write `local_reports/fictional-three-frames.json` based on this pattern
(substitute all frame-specific screen measurements yourself and use at least
four distinct anchors per capture):

```json
{
  "frames": [
    {"frame_id":"mock-1","anchors":[
      {"id":"A","level_xy":[0,0],"screen_xy":[10,20]},
      {"id":"B","level_xy":[10,5],"screen_xy":[30,5]},
      {"id":"C","level_xy":[40,25],"screen_xy":[90,-55]},
      {"id":"D","level_xy":[90,55],"screen_xy":[190,-145]}
    ]},
    {"frame_id":"mock-2","anchors":[
      {"id":"A","level_xy":[0,0],"screen_xy":[40,-5]},
      {"id":"B","level_xy":[10,5],"screen_xy":[60,-20]},
      {"id":"C","level_xy":[40,25],"screen_xy":[120,-80]},
      {"id":"D","level_xy":[90,55],"screen_xy":[220,-170]}
    ]}
  ]
}
```

```sh
PYTHONPATH=src python -m heman_tools.multiframe_alignment \
  --frames local_reports/fictional-three-frames.json \
  --out local_reports/fictional-crossframe-summary.json \
  --max-residual-px 2 \
  --max-relative-scale-drift 0.02

PYTHONPATH=src python -m unittest discover -s tests -v
```

All input/output JSON is restricted to the gitignored `local_reports/`
root, and the summary omits the original anchor coordinates. No original
IPA, sprites, maps, screenshot pixels or manually measured proprietary
coordinates belong in GitHub or GitHub Actions.

## Verification boundary

This stage depends on the Stage 060 single-frame fitting interface.
**15 new asset-free unit tests** cover camera translation, scale drift,
wrong identifiers, missing landmarks, rotation, duplicated frame IDs,
measurement noise, private CLI paths and input/output aliasing. Independent
CI must pass before merging this stage. No real iOS frame evidence is
supplied in the public tests, and no original physics is inferred.
