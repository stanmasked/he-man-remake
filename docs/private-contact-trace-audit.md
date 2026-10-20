# Stage 076 — controlled contact-trace comparison (evidence only)

An original-game physics match needs **two independently observed,
time-aligned captures**. Stage 076 adds a strictly observational comparison
of the same scripted input sequence, once from the user's iOS game and once
from the Switch prototype. It does not record or fake those captures.

## Input and private processing

Create an input JSON in the gitignored local_reports directory:

- Top-level: \`scenario_id\`, integer \`fps\` (1–240), and two captures
  \`reference\` and \`candidate\`.
- Each capture: \`platform\` (\`ios\` or \`switch\`), unique \`capture_id\`,
  \`evidence_kind\` (\`synthetic\` or \`manual_observation\`),
  \`stationary_anchor_id\`, and positive \`pixels_per_unit\` derived from a
  **separately evaluated** coordinate-calibration hypothesis.
- Every capture has **8–600 contiguous frames starting at zero**, each with
  \`frame\`, \`control\` (\`horizontal\` -1/0/1 and \`jump\` boolean),
  \`feet_screen_xy\`, \`anchor_screen_xy\`, and explicit contact label:
  \`airborne\`, \`floor\`, \`wall\`, \`ceiling\`, \`one_way\`, \`hazard\`, or
  \`unknown\`.

Example frame for a **fabricated** test (not actual He-Man):
\`\`\`json
{
  "frame": 0,
  "control": {"horizontal": 1, "jump": false},
  "feet_screen_xy": [20, 35],
  "anchor_screen_xy": [10, 15],
  "contact": "airborne"
}
\`\`\`

The comparator subtracts the stationary anchor's screen position from the
hero's feet position *within each capture*, then divides by the explicitly
provided pixels/unit calibration. It rejects different per-frame inputs,
invalid numeric values, frame omissions, inconsistent anchor identities or
duplicated capture IDs. It measures RMS/maximum relative-position discrepancy,
contact-label disagreements and disagreement in contact transitions.
An \`unknown\` contact cannot produce a clean numeric pass.

\`\`\`sh
PYTHONPATH=src python -m heman_tools.contact_trace_audit \
  --traces local_reports/private-traces.json \
  --out local_reports/private-contact-comparison.json \
  --max-position-error-units 1.0 --max-contact-mismatches 0

PYTHONPATH=src python -m unittest discover -s tests -v
\`\`\`

Both input and output must stay in ignored \`local_reports/\`. The output
contains aggregate errors and mismatch counts **not raw screen coordinates,
captured frames or original imagery**. All CI inputs are fabricated; nothing
is an authenticated original iOS gameplay trace.

## Evidence limits

Numeric agreement **cannot authenticate** frame provenance, stationary
landmark identity, correct pixels-to-world calibration, the meaning of a
contact label, source-game physics or collision tile semantics. It does not
prove the Switch recreation matches the original, even with zero error.
Manual source-private review is mandatory, in addition to all eight distinct
checks of \`docs/first-level-evidence-gate.md\`.

Reports explicitly retain
\`source_capture_authenticated = false\`,
\`original_ios_physics_verified = false\` and
\`automatic_collision_export_permitted = false\`.
The tool does **not** alter the playable Switch prototype or original IPA.
