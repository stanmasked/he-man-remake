# Stage183 — real-time Switch app-clock probe

This is a separate, synthetic-only Nintendo Switch NRO for validating the real libnx monotonic counter against the Stage182 portable app-clock bridge. It is not a playable He-Man remake and contains no original game assets.

## Build

The CI workflow uses the devkitPro Switch SDK and creates:

`switch_realtime_clock_probe/heman_realtime_clock_probe.nro`

The NRO is uploaded as a short-lived GitHub Actions artifact. Cross-compilation and NRO header checks do not establish that it runs correctly in NeXium or on hardware.

## Real-counter self-check

At startup, the probe uses libnx `armGetSystemTick()`, `armGetSystemTickFreq()`, and `armTicksToNs()`. It samples the counter, deliberately stops dispatching the app clock for 500 ms, and then for 200 ms. Each observed counter interval must be at least as long as the requested sleep, then each resumed dispatch must be capped to 66 ms and consume four 16-ms scheduler updates with a 2-ms remainder. An additional 16-ms callback runs with the player clock paused: the app scheduler must still consume updates while player time remains unchanged. A final active callback checks normal animation resumption. The sprite clock advances by exactly 40 synthetic player-clock units per active scheduled update.

The dedicated workflow now builds the NRO, runs it in a temporary checkout of pinned NeXium, captures genuine guest framebuffer PNGs, and uses OCR to require the startup PASS marker in a late guest frame. The workflow result is the evidence gate; cross-compilation alone is not runtime proof.

## Interactive checks

- **A** toggles the application-level dispatch gate. While off, the probe deliberately skips clock sampling and scheduler advancement; the next dispatch should see a capped pause interval.
- **X** toggles only the player clock. The app scheduler continues to run while animation time remains paused.
- **B** resets the synthetic clock state and establishes a fresh baseline.
- **+** exits.

The existing deterministic Stage172 sprite-clock NRO and its exact-pixel oracle are unchanged. The real-time probe has its own directory, Makefile, NRO build artifact, NeXium runtime job, and retained evidence artifact. The runtime check is isolated from the deterministic Stage172 pixel oracle.
