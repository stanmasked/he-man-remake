# Stage194 — native TextureData wrap modes versus residual SpriteCut bounds

Stage194 investigates whether the remaining cuts outside allocated texture dimensions intentionally rely on texture wrapping. The native field mapping and a paired private census now rule out GL_REPEAT as the explanation for those exceptions.

## Native ARMv7 evidence

The original `TextureData::customLoad` reads the two wrap IDs from byte offsets 10 and 11 of its 13-byte scalar block:

- ID `0` maps to `GL_CLAMP_TO_EDGE` (`0x812F`).
- ID `1` maps to `GL_REPEAT` (`0x2901`).
- Other IDs map to the native `-1` sentinel; the model does not guess their effective mode.

`Texture::activate` compares these stored settings independently and applies them to `GL_TEXTURE_WRAP_S` (`0x2802`) and `GL_TEXTURE_WRAP_T` (`0x2803`). Thus wrap configuration is explicit per texture; the bounds audit can correlate a cut to the exact native wrap pair without extracting pixels.

## Private original-data results

Each resolution pack has 1,645 TextureData records and 2,334 indexed SpriteCut tuples. The wrap-code distribution is identical across both packs:

| Texture wrap pair | TextureData records per pack | Cut tuples per pack |
|---|---:|---:|
| CLAMP_TO_EDGE / CLAMP_TO_EDGE | 1,632 | 2,332 |
| CLAMP_TO_EDGE / REPEAT | 6 | 1 |
| REPEAT / REPEAT | 7 | 1 |

Bounds by wrap pair:

| Resolution and wrap pair | Inside raw PNG | Fits allocated only | Outside allocation | Invalid geometry |
|---|---:|---:|---:|---:|
| screen-med — CLAMP / CLAMP | 2,289 | 37 | **5** | 1 |
| screen-med — CLAMP / REPEAT | 1 | 0 | 0 | 0 |
| screen-med — REPEAT / REPEAT | 1 | 0 | 0 | 0 |
| screen-xlarge — CLAMP / CLAMP | 2,252 | 63 | **16** | 1 |
| screen-xlarge — CLAMP / REPEAT | 1 | 0 | 0 | 0 |
| screen-xlarge — REPEAT / REPEAT | 1 | 0 | 0 | 0 |

All 5 medium and 16 extra-large cuts that exceed even the original power-of-two allocation use **CLAMP_TO_EDGE on both axes**. None use GL_REPEAT. The one negative-Y invalid rectangle in each pack also uses CLAMP_TO_EDGE on both axes.

This means the remaining exceptions are **not explained by intentional repeat wrapping**. It does not prove they are corrupt: the original renderer could still clamp them to the edge, or another source-level convention could explain them. The audit therefore leaves their geometry unchanged and unresolved.

## Implementation

Added `src/heman_tools/sprite_cut_wrap_bounds_audit.py`:

- reads the two native wrap codes from the already-validated 13-byte TextureData scalar block;
- follows each indexed SpriteCut handle to its TextureData wrap pair in memory;
- joins the private wrap map to Stage192's raw-PNG/power-of-two geometry classifications;
- requires paired cut-handle identities and wrap settings to agree across both resolution packs;
- reports aggregate counts only, with no keys, paths, offsets, source bytes, per-record values or images;
- never clips, repairs, or renders an unresolved cut.

Added 16 synthetic-only tests, including complete fabricated two-resolution IPA fixtures for clamp/repeat grouping, mismatched wrap settings, and missing PNG failure. The original IPA was used only in the local private census; it is not uploaded or committed.

Owner-private command:

```sh
PYTHONPATH=src python -m heman_tools.sprite_cut_wrap_bounds_audit \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/stage194_wrap_bounds.json
```

## Next steps

1. Inspect the remaining cut rectangles and their source-resource dimensions only as aggregate geometry; do not export their identifiers or pixels.
2. Determine whether the original frame renderer deliberately accepts out-of-allocation UVs or whether these are unresolved source-data exceptions.
3. Continue with a private multi-symbol composition prototype using the Stage193 color/easing/mask contract and the Stage192 allocated-dimension UV denominator. The first composed frame must still be compared privately against authentic source rendering before claiming visual parity.
