# Stage 033 — NeXium standard NRO0 loader compatibility

This work contains a **source-only upstream fix proposal**, plus a separate
Python reference model with regression tests. It is not a forked NeXium
binary or a claim that He-Man already runs in NeXium.

## Verified case

The independently authored minimal devkitPro homebrew app emits a real
`106496`-byte (`0x1A000`) image with:

| Physical offset | Meaning |
| --- | --- |
| `0x00000` | 16-byte `NroStart` entry/metadata stub |
| `0x00010` | `NRO0` header |
| `0x00020` | Text segment offset = 0, size = `0x14000` |
| `0x00028` | RO segment offset = `0x14000`, size = `0x4000` |
| `0x00030` | Data segment offset = `0x18000`, size = `0x2000` |
| `0x1A000` | End of code image and physical file |

The loader in pinned upstream NeXium commit
[`b6149f64`](https://github.com/nexium-emu/nexium/commit/b6149f647f1b0824e450555beb6cfc16b6f0e075)
correctly locates `NRO0` at +16, but incorrectly uses the
*slice beginning at the header* as the origin and bounds for the code
segments. Thus the legitimate file data segment ending at `0x1A000`
is incorrectly checked against a slice with length `0x19FF0`.
The loader also incorrectly adds 128 to a text offset of zero.

Switchbrew's [NRO0 description](https://switchbrew.org/wiki/NRO0)
and [libnx NroStart/NroHeader source](https://switchbrew.github.io/libnx/nro_8h_source.html)
confirm that `NroStart` lives at physical byte zero and the segment
offsets are within the **full NRO image**.

## Proposed upstream change

`patches/nexium-nro-segment-file-origin.patch` changes only
`nexium-loader/src/nro.rs`. It:

- keeps reading header fields at the detected `NRO0` position;
- validates segment ranges against the *declared code image size*
  rather than the shortened header-relative slice;
- reads the three segments at their physical file offsets without
  adding +16 or +128;
- rejects invalid segment order and offset overflow;
- returns the whole declared NRO code image from `nro_bytes()`.

This is a **candidate source patch**; it must be reviewed and tested in
NeXium upstream. The separate `verify-nexium-patch.yml` GitHub Actions
job checks that it applies to exactly the pinned Rust source, but it
does not compile or run a modified emulator.

## Testing and scope

`python3 -m unittest discover -s tests -p test_nro_loader_reference.py -v`
validates header offsets, full-file text/RO/data slices, valid adjacency,
truncation, overlap, malformed segment sizes and trailing ASET resources.

**Never patch the distributed He-Man `.nro`, append padding to silence
validation, ship emulator firmware/keys, or publish the original IPA.**
A passing reference model or source-patch check is not proof that
NeXium can execute the homebrew; actual guest framebuffer capture
remains the runtime acceptance test tracked in
[Issue #30](https://github.com/stanmasked/he-man-remake/issues/30).
