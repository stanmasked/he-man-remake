# Stage 112 — VERIFIED real pinned NeXium guest lore-lab route

**Result: PASS, 2026-10-21**. The third calibrated real guest run
[GitHub Actions #39603358966](https://github.com/stanmasked/he-man-remake/actions/runs/39603358966)
succeeded in all four jobs. This closes **only** the standalone synthetic
Switch lore-lab guest-integration test; original iOS Level 1-1 fidelity
remains unverified and privately gated in [Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).

## Reproducible, independently inspectable guest artifacts

- [Actual frame_rx PNGs, original production runner logs and checksums](https://github.com/stanmasked/he-man-remake/actions/runs/39603358966/artifacts/12348217809)
- [Compiled AArch64 NRO artifact](https://github.com/stanmasked/he-man-remake/actions/runs/39603358966/artifacts/12346638881)
- [Full main CI #39603359222](https://github.com/stanmasked/he-man-remake/actions/runs/39603359222): **all five SUCCESS**, Python 3.10, 3.12 and 3.13 each 982/982, native C99 GCC and Clang PASS.
- The guest NRO SHA-256 remained `746937707eb7da2a8761d4e98b50be3e57d3cbb0691258d02e64f0a61004eb4b` before/after the NeXium run.
- Pinned NeXium kernel `[hid-publish]` independently confirmed 21 real shared-memory samples containing the 20 scheduled button edges (DRIGHT, DLEFT, B, X, Y, L, R, including neutral releases). Runner-only scheduled file writes were NOT accepted as proof.
- The real pinned `debug_boot` run executed guest AArch64 CPU instructions and SVCs, captured 12 real 640×360 `frame_rx` PNGs at the expected paths. The Python checker validated their actual source-rendered pixels.

## Native source-fictional progression, verified on real guest pixels

The table below was **independently measured from PNG RGB pixels** in the successful NeXium artifact, not synthesized by host tests. `x` is the tutorial `hm_state.x` position derived from the 10-pixel yellow player marker; five lights are (Wall Crusher, gate, Bio, Concept Art, in-RAM save). There are **no original iOS map positions** in this table.

| Guest frame | Player x | HUD lights | Earned lore count | Explanation |
| --- | ---: | --- | ---: | --- |
| 30 | 24 | 00000 | 0 | New synthetic lab session |
| 60 | 52 | 00010 | 1 | Free Concept Art earned |
| 130 | 176 | 00010 | 1 | Bio native bit previously touched but reward blocked |
| 165 | 176 | 00011 | 1 | L stores RAM snapshot |
| 215 | 24 | 00001 | 0 | B restarts player, RAM save kept |
| 265 | 176 | 00011 | 1 | R restores saved session |
| 305 | 176 | 10011 | 1 | Y grants **debug-only** Wall Crusher |
| 345 | 110 | 10011 | 1 | Hero returns toward physical gate |
| 395 | 100 | **11011** | 1 | Actual fresh X inside native contact opens gate |
| 445 | 158 | **11111** | **2** | Genuine return to formerly blocked Bio earns second reward |
| 485 | 158 | 11111 | 2 | L saves completed progression |
| 530 | 158 | 11111 | 2 | R restores with no duplicated reward |

Both full-pixel RGB SHA-256 comparisons succeeded:

1. `raster-frame-0165.png` = `raster-frame-0265.png` (initial RAM save, B reset, R load).
2. `raster-frame-0485.png` = `raster-frame-0530.png` (fully earned RAM save and R load).

## Correctness history

Prior real guest #39596130343 **correctly failed** the gate visual oracle:
player center x≈115.5 was outside the native gate AABB/radius sensor
(center x104, actor half-width5, sensor radius4). The second actual
run #39600185389 also **correctly failed** at x94, now just one pixel
left of the permitted interval `[95,113]`. Neither failure was
hidden or excused; both captured kernel NPAD and original framebuffer
evidence. The final controller-only DLEFT release at guest frame350
(earlier iterations had 342 and 352), with X at365, produced x100 and
the observed true gate-opened frame395. **The C99 collision algorithm,
event role binding, game NRO, and optical oracle were not relaxed**.

## Strict limitations

This success proves real **NeXium emulator** execution of the authored
**standalone fictional lab**. It does **not** prove running on Nintendo
Switch hardware, original iOS art assets, the original game level,
original collision positions, original capture timing, original
save format, original upgrade acquisition or source fidelity. Only
hand-authored colored rectangles, synthetic events and a RAM-only
96-byte lab save were shipped. The private original IPA was not
loaded or uploaded. The stable two-room and earlier three-room
guest-verified NROs remain untouched.

Do not merge this stacked draft into a release branch as evidence of
source-accurate original iOS Level 1-1.
