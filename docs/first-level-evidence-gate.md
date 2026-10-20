# Stage 063 — first-level collision evidence gate

Before transforming candidate geometry from the privately studied
`MULevel1-1.lvl` into the Switch runtime, reviewers must explicitly
establish **all eight distinct forms of evidence**:

1. Level object identity and correct object instance.
2. Shape-to-object ownership.
3. Coordinate and measurement scale.
4. Origin and axis orientation.
5. Cross-frame consistency.
6. Independent held-out point validation.
7. Real collision category (solid, one-way, sensor, hazard etc.).
8. Comparative trace of original iOS gameplay behavior.

The read-only `level_evidence_gate.assess_geometry_evidence()` function
identifies which declarations are missing. Missing entries and `false`
values are both treated as unverified. It rejects unknown keys and
truthy non-boolean values. Even when all are true, the tool allows
**manual review only**; automatic collision export is always disabled.

These declarations are not authenticated by this software. Screenshots,
private IPA data, decoded maps, traces and derived actual measurements
must be inspected separately and remain outside public GitHub. No
evidence declarations for real gameplay are supplied in this repository.

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

The eight accompanying synthetic unit tests ensure that numerical
calibration alone cannot be treated as established game physics.
This stage changes no Switch engine or real collision behavior.
