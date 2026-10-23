# Stage218 — four-view original-source frame parity gate

## Goal

With Stage216 owner-private application resources independently archived and
read back, repeat the CPU pipeline on an actual iOS animation sequence for
four views: east/west direction and medium/extra-large resource packs.

Original source evidence and all selected resource identifiers remain
**owner-private**. The public code is synthetic-only and contains no extracted
PNG, sequence alias, byte range, texture name or per-resource hash.

## Owner-private evidence checkpoint

The original 137,274,848-byte IPA was checked against its separately recorded
SHA-256 and the Stage216 complete-source ZIP integrity result. A selected
original sequence pair was resolved using its native `SpriteSeqData.repo`
index and bounded `go/default` references, not invented aliases.

Four original-source records decoded successfully with the Stage214 owner-local
PNG/CPU reference renderer: two directions in each screen pack. Every selected
view had the expected two-layer ordered packet structure; all original PNGs
and SpriteCut rectangles used in the views were validated. Cropped CPU preview
dimensions were exactly 2:1 between packs for both directions. The selected
west-facing source Symbols had negative local X scales while the corresponding
east-facing Symbols did not. These observations apply to **the selected
sequence only**, not every character, frame or game scene.

Privately retained:
- `02_Raw_Traces_and_Captures/Stage218_original_frame_probe/`: four original
  cropped CPU preview PNGs plus the private source selector (alias and GO
  byte bounds).
- `03_Aggregate_Reports/Stage218_original_frame_probe/`: an aggregated
  four-view report plus a small source-frame validation report.

These reports were produced using the Stage214 owner-local source snapshot and
explicitly audited Symbol contracts. Stage217's optional synthetic
SpritePlayer-wide transform experiment is **not** an original runtime capture.

## Public Stage218 gate

`heman_tools.four_view_frame_parity_gate` accepts aggregate-only, owner-local
four-view JSON and returns:
- complete resolution × direction coverage and rejection of duplicates;
- Symbol count, resolved Symbol count and draw-packet count comparisons across
  the source-resolution pair in each direction;
- explicit booleans for exact doubling of **cropped canvas** dimensions;
- counts-only consistency of negative local X scales, when that metric exists.

Mismatches are reported, not replaced by synthetic geometry. The gate will not
read or publish source bytes or pixels. It rejects any CPU report purporting
to have verified GPU execution or original runtime pixel parity. The output
always records camera, player-wide runtime transform and pixel parity as
unverified.

The local command, after preparing a four-frame aggregate containing
`frames`, is:

```sh
PYTHONPATH=src python -m heman_tools.four_view_frame_parity_gate \
  --source-report local_reports/stage218-original-four-frame-report.json \
  --out local_reports/stage218-public-safe-metrics.json
```

Source and destination both stay under ignored `local_reports/`. Public CI
exercises invented four-frame metrics, including malformed, incomplete,
unpaired, size-mismatched and false-runtime-parity cases.

## What this cannot prove

An exact 2× relationship between trimmed CPU canvases is not the same as
pixel-level agreement after hardware filtering, original iOS screen placement,
native camera or SpritePlayer pivot/recenter state, physics synchrony,
full-scene rendering or a playable game. This stage does not recover runtime
camera values and does not use iOS emulator frame capture as its oracle.

The next evidence gate is an authentic full-screen iOS runtime image/trace
with a documented animation timestamp and player/camera transform. Do not
substitute cropped source sprite PNGs or synthetic transforms for that evidence.
