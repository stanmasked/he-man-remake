# Stage181 — application-state gate and bounded resume

Stage181 adds a source-free native regression for a second pause path identified in the private original iOS executable. This is distinct from Stage175's player-level pause flag.

## Static behavior being modeled

The original `HeloApp::_tick` path skips dispatch to `GSAppDelegate::onTick` when the application-state field is nonzero. The handler owns a separate wall-clock sample and the 66-ms-capped accumulator described in Stage179. If the handler is skipped, its wall-time baseline is not refreshed by that handler. On the first active callback, the elapsed interval can therefore include the paused period.

This is a static call-path interpretation, not a measurement of iOS suspension or callback delivery. The test uses only fabricated time deltas.

## Regression

The C99 integration test now distinguishes the two pause cases:

- **Player-level pause:** scheduler callbacks continue, but the sprite clock receives an inactive flag and does not advance.
- **Application-state gate:** handler dispatch is skipped for 30 fabricated callbacks whose 16/17/17-ms pattern totals 500 ms. The first resumed handler receives that elapsed interval; the existing 66-ms cap yields four 16-ms updates and a 2-ms remainder.

The regression checks that the skipped period does not mutate the accumulator or player clock, and that resumed catch-up remains bounded. It does not add a production clock adapter or change the Switch NRO.

## CI trigger scope

The room-2 NeXium workflow builds its guest NROs from `switch_minimal`, `switch_raster`, `raster`, the native source/header files, and the Switch adapter sources. It does not compile `native/tests/**` or execute `native/run_tests.sh`. Those two broad path filters caused unrelated host-test-only edits to queue an expensive guest build. Stage181 removes those two triggers while retaining source and verifier paths used by the workflow. The workflow file itself remains an explicit trigger, so this PR still matches that path; future native test-only edits will not trigger the room-2 guest workflow by themselves.

## Verification boundary

The test is compiled by `native/run_tests.sh` with strict C99 warnings under both GCC and Clang. It validates the source-free scheduler model only. Actual NeXium guest execution remains a separate gate, and original-device timing parity remains unmeasured.

No original IPA bytes, disassembly, art, extracted resources, or private reports are committed or uploaded.
