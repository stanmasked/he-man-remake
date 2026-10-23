# Stage210 — C99/Python textured-quad parity

## Goal

Compare the Stage208 C99 renderer and Stage207 Python oracle against the same synthetic frame, so the Switch probe is backed by a byte-level cross-language test rather than separate hand-written expected outputs alone.

## Test

`tests/test_c99_textured_quad_parity.py` builds the C implementation as a temporary host shared library using the CI compiler, binds the same packet/texture/projection/blend values through ctypes, and compares every active RGBA output byte with `render_textured_frame`.

The fixture exercises two texture slots distinct from cut handles, nearest sampling, clamp and repeat, out-of-range UVs, clipping at the right framebuffer edge, explicit projection translation, source-order composition, per-Symbol blend override and nonzero clear color. It also checks packet/pixel counters and confirms all row-padding canaries survive.

The shared library exists only in the temporary test directory. No original IPA, extracted texture or private frame report is loaded or exported.

## Evidence boundary

A passing differential test establishes parity for this synthetic fixture only. It does not establish GLES triangle-edge behavior, GPU upload orientation, source alpha representation, original-runtime pixels or physical Switch execution. The Stage209 NeXium workflow remains the separate guest-frame integration check.
