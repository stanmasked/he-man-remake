# Stage 112 — genuine NeXium guest evidence for the synthetic lore lab

The prior Stage111 PR #119 built `switch_lore/heman_level11_lore_lab.nro`
with libnx and verified its AArch64/NRO0 format; compilation alone did
not prove it ran in NeXium.

Stage112 adds a **separate, opt-in pinned emulator workflow**
`.github/workflows/nexium-patched-lore-lab.yml`. It reuses the exact
already proven NeXium SHA
`b6149f647f1b0824e450555beb6cfc16b6f0e075`, applies only the
known loader patch and instruments temporary `debug_boot.rs`
receiver loops to save real `frame_rx` PNGs and schedule input-text
packets. It never patches or repaints the NRO.

## Real guest verification required

- The actual source-authored Stage111 NRO is built in the
  devkitPro AArch64 CI job alongside a minimal baseline probe.
- The kernel's original NPAD HID source layout, shared-memory masks
  and `[hid-publish]` trace format are checked **before** compiling
  NeXium. Real kernel samples must confirm the entire scheduled
  `DRIGHT,L,B,R,Y,DLEFT,X,DRIGHT,L,R` sequence and every release.
  Runner-side `HEMAN_LORE_HID` messages do not suffice.
- The NeXium runner must report nonzero guest cycles and SVC calls.
  Every stage optical sample must be the unaltered 640×360
  `frame_rx` PNG at the exact logged absolute path.
- `tools/verify_nexium_lore_lab_pngs.py` samples the **actual NRO
  source framebuffer colors**, five independent status lights,
  earned-lore-count HUD, ten-pixel player location, and RAM-save
  indicator. It requires a series of visual transitions from
  initially no rewards to Concept Art earned, save, B restart,
  R restore, Y explicit synthetic upgrade, return to previously
  touched gate, fresh X attack, both lore rewards earned, a second
  L/R save/load, and stable duplicate-free rewards.
- Independent pre/post NRO SHA-256 checks prevent replaying a
  silently changed NRO between capture phases. All failure logs
  and PNGs are uploaded as short-lived CI artifacts.

The 20 scheduled HID states are **hypotheses about emulator host
polling versus guest frame cadence**. The pinned HID injector may
poll its file only every 25ms; a fast or differently paced guest
can miss a packet. Any missing pressed/release state, inconsistent
optical milestone, missing guest-frame PNG, zero CPU/SVC progress or
conflicting NRO digest **fails CI**, not auto-corrects a result.

The Python `tests/test_nexium_lore_lab_evidence.py` suite uses
**fabricated logs and mocked images only**. It tests both success
contract logic and negative failures, but **is not NeXium evidence**.
Only a successful real `headless-guest-runner` job with matching
kernel NPAD memory and guest `frame_rx` files can establish genuine
NeXium execution of the Stage111 lab.

## Original iOS fidelity is still NOT proven

The lab world is source-authored fictional debug data, with a
synthetic Wall Crusher upgrade on Y, no original level art, no
commercial map geometry and a RAM-only save slot unrelated to the
original iOS persistence scheme. Its guest runtime success, even
if achieved, establishes this **independent mechanics integration
test only**, not a recreation of original iOS Level 1-1. The
user-owned IPA is never uploaded to GitHub/CI. Real original object
identities, scale, camera and collision/hit timing remain blocked
in [Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).

Historical reference: Stage101's
[real three-room NeXium guest proof](https://github.com/stanmasked/he-man-remake/issues/97)
is independent and remains unchanged. The stable two-room and
original guest three-room test builds are not modified.
