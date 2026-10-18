# Stage 009 — full-body collision harness (host-only)

This module extends the previous feet-only mask approximation with a rectangular character collider. It is a separate experimental API and does **not** replace the original game physics. No original IPA, maps, shapes, textures or private reports are included in GitHub.

## Implemented

- Character rectangle defined by center X, foot Y, half-width and height.
- Half-open occupied rectangle, so feet exactly at a tile top do not overlap it.
- Axis-separated horizontal and vertical sweeps in steps of at most one pixel, followed by a binary refinement on collision.
- Left and right wall contacts, underside ceiling contacts, grounded support, gravity, jump and ledge fall.
- Static collisions over pixel-level masks, with initial-overlap rejection instead of automatic teleportation.
- Limits on body dimensions and travel per tick against malformed inputs.
- Deterministic fixed-step host simulation, normally 1/60 s.
- An optional **local-only** IPA diagnostic that generates no public game data.

## Validation

The Stage 009 host suite has **122 tests**, including 22 new synthetic cases (17 body tests, 5 script-driver tests). New cases cover horizontal tunneling, wall approaches from both directions, jumping into a low ceiling, subsequent fall, ledge transitions, contact exactly at tile boundaries, head overlap, repeated deterministic simulation and invalid parameters.

Private integration using the supplied iOS 2.0.0 IPA:

- MUMap1-1.map grid: 300 columns × 19 rows, tile size 32.
- Collision layer: 790 occupied cells with tile-mask IDs 3–8.
- Experimental probe with invented X=50 / feet Y=0, body half-width=5 and height=22, after 240 fixed ticks: feet Y approximately 448, one landing.
- This is NOT the original character spawn, original hitbox size, or validated movement rate.

## Limitations

Not yet supported: exact He-Man collision box, physics constants, one-way platforms, hazard hits, interactions, enemies, moving terrain, sloped-ground adhesion, death-plane bounds, and original camera behaviour. Horizontal motion may stop at a slope rather than climb it. Cells outside the map are currently treated as empty.

## Run synthetic tests

    PYTHONPATH=src python -m unittest discover -s tests -v

## Run privately with your own iOS IPA

Install Pillow in the local environment for PNG decoding, then:

    PYTHONPATH=src python -m heman_tools.body_probe --ipa /private/He-Man-v2.0.0.ipa --map MUMap1-1.map --x 50 --feet-y 0 --ticks 240 --out local_reports/level1_body_probe.json

Original content is opened locally and never uploaded. The local_reports directory is Git-ignored.

## Next research target

Identify real hitbox dimensions and movement constants, reconcile slope walking with full-body collisions, then build a scene simulator before a Switch NRO build.
