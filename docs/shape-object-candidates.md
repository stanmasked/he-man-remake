# Stage 058 — private, unverified shape/object candidate cross-references

The independently decoded iOS `.lvl` object records and local-space `.shape` primitives may share text identifiers. This stage adds a **read-only exact-name comparison tool**. A match is only a **candidate**, never proof of geometry ownership, physical collision behavior, or correct world placement.

## Candidate evidence recorded

For each `.shape` definition in the private `screen-med/geometry` archive group, the tool compares the **exact, case-sensitive** shape filename stem and optional shape reference with each parsed level object's:

- `instance_name`
- Explicitly typed **string** property values

The resulting private report identifies the object indexes and evidence type(s), and separates shapes into `no_exact_candidate`, `one_candidate_only` or `ambiguous_multiple_candidates`. Even one candidate remains unverified. The report intentionally omits polygon vertices, circle radii, local bounds, object matrices, gameplay scripts and original source bytes.

The CLI accepts only a simple `.lvl` filename, a bounded local IPA input, and JSON output beneath the ignored `local_reports/` directory. Duplicate level or shape filenames and nested geometry entries are rejected. Original commercial resources and private candidate reports must never be committed to GitHub.

## Private local command

```sh
PYTHONPATH=src python -m heman_tools.shape_object_candidates \
  --ipa /private/He-Man-v2.0.0.ipa \
  --level MULevel1-1.lvl \
  --out local_reports/level1-shape-object-candidates.json

PYTHONPATH=src python -m unittest discover -s tests -v
```

The test suite uses fabricated `.lvl` and `.shape` buffers inside temporary mock IPAs. No original game byte arrays, geometry, art, sound, screenshots or executable code are stored publicly.

## What remains unresolved

- Whether a shape's optional `reference` identifies a tilemap, reusable geometry definition, collision sensor, physical body or unrelated resource.
- Which level instance, if any, owns each shape; a shared string could be incidental.
- Orientation, units, 3×3 transform application, pixel-to-world scale and dynamic/one-way collision semantics.
- Correlation with source-private tile alpha, frame-by-frame physics and authoritative runtime behavior.

Only after independent private comparisons should a candidate become an explicitly reviewed object/shape association. The synthetic Switch scene is not equivalent to the original iOS campaign.
