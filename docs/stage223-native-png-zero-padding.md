# Stage223 — original ARMv7 PNG zero padding and CPU reconstruction

## Verified original executable behavior

The owner-private `He-Man-v2.0.0.ipa` (137,274,848 bytes)
was independently checked against its pinned SHA-256 before examining its
ARMv7 Mach-O executable. The original `helo::pngInfoCallback` computes
minimum-four next-power-of-two allocations, then makes **two
`memset(..., 0, ...)` loop calls**: one zeroes all extra bytes at the right
of each decoded PNG row; the other zeroes complete rows beneath the actual
image. The verified imported stub resolves to `_memset`, not a guessed
copy/initialization routine. `helo::pngRowCallback` combines decoded PNG
rows into the buffer using **allocated width × native channel count** as its
row stride.

The same code branches into native three-channel (RGB) and four-channel
(RGBA) upload formats. The zero native bytes thus represent opaque black
when an RGB upload is sampled by GLES (implicit alpha 1) and transparent
black for RGBA (native zero alpha). Original iOS GPU frame/camera parity
is still unverified. Complete disassembly and exact code offsets remain
private.

## Owner-original texture inventory

All PNGs in both screen packs were decoded and their original native
PNG alpha presence and allocated footprints checked:

| Original PNG textures | screen-med | screen-xlarge |
|---|---:|---:|
| Total | 1,644 | 1,644 |
| Requiring native zero padding | 1,004 | 1,002 |
| Padded native RGB | 99 | 105 |
| Padded native RGBA | 905 | 897 |
| Exact allocation match | 640 | 642 |

These are counts of original PNG resources, not SpriteCut bindings; the
Stage221 padded-cut counts use a different denominator. The largest
individual native allocated texture in the original data remains within
the 64-MiB CPU reference safety limit.

## Public implementation

`native_png_zero_padding.reconstruct_native_zero_padded_texture` builds
the allocated-row-stride RGBA CPU representation from an explicitly validated
native upload layout and separately reported source PNG alpha presence.
Every original visible PNG row is preserved exactly.

For an original RGB PNG, extra sampled pixels become (0, 0, 0, 255);
for an original RGBA PNG, extra pixels become (0, 0, 0, 0).
The strict Stage222 `prepare_native_cpu_texture` guard remains in place
and independently checks every visible source row and allocation size.
False RGB alpha, malformed source buffers, wrong dimensions and unsupported
sampling modes fail closed.

Owner-local source frame audit now propagates the actual PNG alpha presence
only in the private in-process collector. The CPU preview uses the verified
native padding model and continues to export aggregate-only provenance
and explicit false GPU/runtime parity flags.

Tests contain invented RGBA and RGB pixels, including minimum-four,
power-of-two and padded-stride cases; an additional synthetic IPA checks
the full PNG decoder → native allocation → CPU preview path.

Private exact executable evidence, verifier scripts, and detailed PNG-mode
census are archived in owner-only Google Drive, not public GitHub.

## Scope and next stage

This resolves **what the original native PNG reader wrote to its padded
bytes**. It does not prove the output of every original GPU code path,
shader/filter behavior, original live camera state, or Nintendo Switch GPU
pixel parity. Next, use this verified CPU texture upload path in a
controlled Switch raster/GPU probe and compare authentic, timestamp-aligned
iOS gameplay frames where such evidence exists.
