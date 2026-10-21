# Stage120 — correct a genuine NeXium gate-attack undershoot

On 2026-10-21, the real Stage118 [guest run #39654091047](https://github.com/stanmasked/he-man-remake/actions/runs/39654091047)
failed **before** entering its corrupted-SD experiments. The unmodified
Switch NRO ran under pinned NeXium and all 26 expected NPAD transitions were
published, but the independent frame_rx screenshot check was right to reject
the scene at frame 395: the gate still had the inactive color.

Direct inspection of the actual saved PNG artifacts established:

| Actual guest evidence | Frame 345 player x | Frame 395 player x | Gate at 395 |
| --- | ---: | ---: | --- |
| Stage117 [successful #39651499791](https://github.com/stanmasked/he-man-remake/actions/runs/39651499791) | 108 | 96 | opened |
| Stage118 [failed #39654091047](https://github.com/stanmasked/he-man-remake/actions/runs/39654091047) | 106 | 94 | closed |

These are guest screenshot pixel measurements, not expected model output.
The synthetic tutorial's native contact range is approximately x=95–113.
The discrepancy is a **2-pixel positioning undershoot**, not a failed
SD filesystem read and not a failure of the native save format.

The pinned runner's *temporary test-only* D-pad schedule now releases DLEFT
at guest frame **348 rather than 350**, giving about four extra pixels
if two additional 2-pixel native ticks are avoided. This is only a
hypothesis about timing: it must pass again in an **actual** NeXium guest.
The oracle still strictly demands the correct frame 395 gate HUD, subsequent
Bio pickup, full progress, save, independent SD records and cold restore;
we do not weaken any success criteria.

The PNG oracle's HUD failure now also includes the actual visible hero x
coordinate in its diagnostic. The test NRO binary, world geometry, collision
logic, stored content, and original iOS assets are unchanged.

The Stage118/119 stacked guest work may not pass until this preceding route
is stable; tests that stop before the corruption step are **not evidence
about** corruption handling. Mark genuine third/fourth-process recovery as
pending until those steps actually execute and their evidence passes.

No raw save files or original copyrighted assets are committed or uploaded.
