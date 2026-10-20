# Stage 059 — mathematical bounds of unverified affine geometry

The decoded iOS level objects provide **3×3 affine matrices**, and local-space
`.shape` resources provide polygons or circles. Stage 059 introduces
asset-free geometry utilities to calculate hypothetical transformed bounding
boxes. **A textual candidate match between any two source records does not
establish that an object's matrix actually belongs to that shape.**

## Supported calculations

- Polygon: transform each local vertex by the previously decoded column-major
  affine matrix and compute its axis-aligned bounding box (AABB).
- Circle: transform the center, then compute the **exact** axis-aligned
  bounding box of the resulting ellipse, using `r * hypot(a, c)` horizontally
  and `r * hypot(b, d)` vertically for matrix linear entries
  `[[a,c],[b,d]]`. Rotating/shearing only the corners of the original
  circle's square AABB would be incorrect.
- Affine diagnostics: determinant, two transformed basis-vector lengths,
  cosine between the basis vectors, possible reflection and near-degeneracy.
  Reject malformed/projective matrices and numeric overflow.

These are pure mathematical calculations, not proof that the original engine
uses the same transform in collision detection. Units, coordinate axes,
world origin, original player dimensions, actual shape ownership, triggering,
collision types, scripts, and behavior remain **unverified**.

## Synthetic-only verification

```sh
PYTHONPATH=src python -m unittest tests/test_affine_shape_geometry.py -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Twenty new tests cover identity, translation, rotation, reflection, shear,
nonuniform scale, degenerate transforms, malformed matrices, hypothetical
envelope metadata, and invalid shapes. No original game resources or private
reports are copied into GitHub. The functions run on caller-supplied decoded
`Shape` objects and matrices, and **do not read or export IPA files**.

## Next evidence gate

Private comparison of independently verified shape-to-object candidate
relationships, original level coordinate ranges and measured gameplay behavior
must precede any use of these envelopes to produce a world collision map.
Until then, treat every output as an **unverified candidate** and keep the
actual original IPA and extracted assets offline.
