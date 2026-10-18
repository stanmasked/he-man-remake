# Binary `.lvl` format — working notes

**Status:** provisional header structure validated against 39 sampled files from one privately held IPA.

| Offset | Encoding | Interpretation | Confidence |
|---|---|---|---|
| `0x00` | LE u32 | version `1` | high |
| `0x04` | LE f32 × 6 | numeric fields; semantics not established | high for layout, low for meaning |
| `0x1c` | LE u16 | UTF-16LE code-unit count for level name | high |
| `0x1e` | UTF-16LE characters | embedded level filename | high |
| variable | LE u32 | possible serialized record count | medium |
| variable | LE u16 followed by UTF-16LE | first record label | medium |

**Warning:** individual entity boundaries, scripts, collision data, and texture references are not yet decoded. Treat apparent numerical bounds as hypotheses, not established screen dimensions.

Locally, all 39 `screen-med` files were byte-identical to the corresponding `screen-xlarge` level files (SHA-256 comparison). This applies only to the provided iOS v2.0.0 archive.

Original source files and full level bodies are deliberately excluded. Tests use synthetic fixtures.
