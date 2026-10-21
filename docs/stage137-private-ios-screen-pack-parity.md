# Stage137 — locally verified iOS resolution-pack file parity

The private original `He-Man-v2.0.0.ipa` is available only to the
owner, outside public GitHub. This stage compares **original iOS file
packaging**, not gameplay, and does not extract or upload files.

## Private validation (iOS 2.0.0; one personally held IPA)

A local, read-only comparison of `Payload/MOTU.app/screen-med/`
and `Payload/MOTU.app/screen-xlarge/` found:

| Resource section | Paired files | Byte-identical across packs | Different |
|---|---:|---:|---:|
| Level descriptions (`.lvl`) | 39 | 39 | 0 |
| Tilemaps (`.map`) | 214 | 213 | 1 |
| Standalone shape file (`.shape`) | 1 | 1 | 0 |

There were no unmatched names among these three selected file
extensions. The sole differing map is the already documented
`gs_background_sky.map`, which was previously identified as an
exceptional format rather than a normal multilayer tilemap.

**Implication:** level metadata from `.lvl` should not be interpreted
as different level designs for medium versus extra-large screen assets.
The vast majority of `.map` bytes likewise match, while the sky
exception must remain separate. These facts **do not** prove that art
textures, sprite pixel density, coordinates, iOS collision rules or
screen layouts are resolution-independent.

## Reproducible LOCAL-ONLY gate

With Python 3.10+ and a privately accessible original IPA:

```sh
PYTHONPATH=src python -m heman_tools.pack_parity \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --strict-v2 \
  --out local_reports/ios_screen_pack_parity.json
```

The tool streams bounded data from the ZIP into memory only, compares
complete decoded contents, and emits **aggregate counters/booleans**.
Its JSON contains **no private file paths, member names, individual
hashes, extracted files, original bytes, pixels or gameplay values**.
The optional report belongs under `local_reports/` (already ignored by
Git). Never attach the IPA or private detailed reports to Actions,
public PRs or GitHub issues.

The `--strict-v2` mode fails closed unless the archive matches
the privately established structural counts and known sky exception.
If it fails, examine the archive locally; do not loosen the public
check to make an unknown private IPA appear compatible.

The new synthetic test suite creates fake ZIP members **in memory**,
checks missing/duplicate, path-traversal, symlink, size-budget and
unexpected-difference behavior, plus output redaction. GitHub CI
must run only these synthetic fixtures.

## Engineering next steps

1. Build a *local-only* artifact inventory / collision research manifest
   for original `MULevel1-1.lvl` and `MUMap1-1.map`, but keep original
   map tiles, coordinates, collision geometry and object identities
   outside GitHub.
2. Separate independently verified format facts from hypotheses about
   enemy AI, movement speeds, jumps and object triggers.
3. Introduce interface-only adapter contracts, exercised with fake maps
   in CI, before integrating any privately generated geometry on-device.
4. Compare future Switch guest PNGs with an owner's lawful reference
   capture privately. The user has no older iOS device, so a
   complete original device-playback reference is not yet available.

**Boundary:** We have verified archive and test NRO behavior, **not
an actual iOS game port**, not original game physics, and not real
Nintendo Switch hardware gameplay.
