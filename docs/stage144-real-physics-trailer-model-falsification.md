# Stage144 — original trailer evidence falsifies simple fixed-width models

This is a **private-only** investigation of the owner's original iOS v2.0.0
archive, not a source game-port implementation. The original IPA, binary
trailers, inferred original positions, individual names, candidate field
widths, decoded strings and individual checksums remain outside GitHub.

## Actual owner-private source test

The 13 nonempty physics-structure trailers declared 44 group items in
total. Stage143 implemented two strict, hypothetical framing patterns,
both requiring exactly one consistent opaque byte width per group and
exact consumption of the whole trailer.

A read-only private run against **all 13 actual trailers** gave:

| Fixed-width framing result | Number of files |
|---|---:|
| Neither candidate layout fully consumes the trailer | **8** |
| Exactly one candidate matches exact EOF | **4** |
| Two or more candidates fit | **1** |
| **Total** | **13** |

Only **3 of the 11** multi-group trailers had any matching fixed-width
model. Therefore these proposed fixed-width layouts are **falsified as
a universal account** of the 13 original files. A match in the other
files is only syntactic, not verification of actual record fields.

## Deliberately more flexible competing model

Stage144 introduces a second experiment with **different unknown
padding lengths per item**, retaining the same source-constrained
UTF-16 token and exact EOF. Each unknown length is allowed within
0–96 bytes. It counts paths as **0, 1, or 2+**, avoiding combinatorial
explosion and false precision, but never chooses or exports a path.

This deliberately broad hypothesis fits the owner-private trailers
far too easily:

| Variable-width framing result | Suffix after UTF-16 label | Prefix before UTF-16 label |
|---|---:|---:|
| No complete segmentation | **0** | **9** |
| Exactly one complete segmentation | **2** | **0** |
| Two or more complete segmentations | **11** | **4** |

All **11 multi-group source trailers** admit multiple distinct
variable-width suffix segmentations. The two uniquely fitted suffix
cases each contain **only one declared group** — a particularly weak
constraint. That **does not prove** that original trailers contain
length-prefixed names followed by data. It instead illustrates that
a sufficiently permissive model is underdetermined.

No source collision materials, physics joints, hitboxes, shape
ownership or game movement parameters are inferred from these patterns.

## Implemented checks and owner-local command

`src/heman_tools/physics_tail_model_falsification.py` compares exact-EOF
constant-width candidates from Stage143 with bounded variable-width
candidate path counts. It reuses the strict Stage141 record-envelope
parser, Stage142 private opaque extractor and paired archive safety
guards. Resource labels and intermediate byte offsets stay in private
process memory.

Owner-local audit only:

```sh
PYTHONPATH=src python -m heman_tools.physics_tail_model_falsification \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/physics_tail_model_falsification.json
```

The result contains only aggregate counts and permanent `false`
verification gates. `local_reports/` remains gitignored; no original
game resource or report with asset bytes may enter public GitHub.

The 18 artificial tests exercise exact whole-tail consumption,
variable ordering, malformed/insufficient UTF-16, one-group false
confidence, many-to-one ambiguous paths, safety bounds, privacy
redaction and paired ZIP security. CI never reads the owner's IPA.

## Next engineering decision

Reject unrestricted variable-width models as a source of definitive
record boundaries. Next test **independently constrained**, repeatable
framing hypotheses: probable per-item fixed structure lengths,
known source name/reference cross-links, and cross-file validation.
If those do not uniquely and consistently account for all 13 trailers,
retain the unknown sections opaque. Original iOS physics and faithful
Switch collision geometry remain unverified.
