# Stage 047 — adversarial evidence tests for post-respawn X combat

`tests/test_nexium_post_respawn_sword_verifier_negative.py` provides
23 source-only Python unittest cases for the **unchanged** real guest
framebuffer verifier from Stage 046.

- One valid 4-frame contract exercises the full 3→2→2→2 player HP and
  2→1→0→0 enemy HP progression.
- The other 22 tests intentionally mutate one part of the proof and
  require rejection: incorrect HP at any milestone, missing or wrong
  respawn indicator, unexpected world-x motion, missing source marker or
  too few scene colors, corrupted HUD color, absent or malformed PNG,
  missing frame capture, missing first/second X press/release and absent
  runner log.

The tests fake **only** the PNG loader and descriptor while invoking the
same production verifier function used on NeXium-exported frames. The
temporary fixture bytes are deliberately not valid PNG, so these tests
cannot themselves be claimed as guest emulator evidence. No Pillow,
devkitPro, NeXium or iOS game resources are required by source-only CI.

Run locally with:

    PYTHONPATH=src python -m unittest discover -s tests -v

Parent PR #46 runs the separate genuine devkitPro/NeXium screenshot
proof. This PR is intentionally stacked and remains Draft until #46
is verified and merged and the Python 3.10/3.12/3.13 and native GCC/Clang
matrix completes on the current commit.
