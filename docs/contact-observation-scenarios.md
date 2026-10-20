# Stage 077 — five controlled contact observation scenarios

Stage 076 can compare two privately observed frame traces, but an arbitrary
collection of frames might miss the collision events being studied. Stage 077
adds **five fixed, provisional capture protocols** with nominal 60 FPS and
explicit logical controller inputs:

| ID | Nominal frames | Initial setup (must be checked manually) | Event to observe |
| --- | ---: | --- | --- |
| landing | 120 | Hero above a candidate flat surface | airborne → floor |
| jump | 150 | Hero initially grounded, with clear space to jump | floor → airborne → floor |
| wall | 120 | Hero approaches candidate wall from the left | wall contact |
| ceiling | 130 | Hero grounded directly beneath candidate ceiling | ceiling contact |
| ledge | 130 | Hero grounded near a right-side platform edge | floor → airborne |

These timings and controller actions are **provisional experimental plans**,
not an assertion that any original iOS level contains matching geometry at a
given position. The iOS touch controls and Switch buttons must be translated
to equivalent *logical* horizontal (-1,0,+1) and jump (boolean edge) inputs
by independently recording what actually happened. If an attempted original
capture cannot follow the script or reach the expected event, the tool must
report the attempt as invalid or incomplete—not invent a matching trace.

## Inspect the scripted controls

The built-in manifest is source-authored and contains no original game data:

    PYTHONPATH=src python -m heman_tools.contact_scenarios --describe

Each horizontal interval is half-open [start,end), and a jump-edge frame
means a one-frame jump press. To avoid confusing scenery motion with hero
motion, each frame records a corresponding **same-identity stationary
landmark** and separately obtained scale in pixels per world unit. This is
still an unverified measurement hypothesis.

## Prepare private capture files

Follow the JSON schema in docs/private-contact-trace-audit.md, using the five
protocol IDs. Record 8–600 frames, but for these five predefined protocols
the required sample count is **exactly** the value listed above. Record all
frames with the scripted inputs and label observed contacts explicitly:
airborne, floor, wall, ceiling, one_way, hazard, unknown.

Run one pair of matched privately obtained traces:

    PYTHONPATH=src python -m heman_tools.contact_scenarios \
      --traces local_reports/private-one-scenario.json \
      --out local_reports/private-scenario-results.json

Run all five once they actually exist:

    PYTHONPATH=src python -m heman_tools.contact_scenarios \
      --suite --traces local_reports/private-five-scenarios.json \
      --out local_reports/private-suite-results.json

The suite input uses {"traces": [ ... five scenario records ... ]}. The
checker requires each scenario exactly once and ten distinct capture IDs.
It verifies scripted input frames, presence of required contact states and
transitions in **both** records, then reuses the stage-076 positional/contact
comparator. Missing events, unexplained contact types and positional drift
are blockers. The tool does **not** generate genuine iOS observations.

The input and derived reports must remain in the gitignored
local_reports/ directory; do not commit real gameplay coordinates, screenshots,
video, original IPA data, or proprietary textures.

## Evidence and review gate

CI tests (24 new tests) construct **artificial** traces solely to exercise the
validator. Numeric and event contract satisfaction on supplied data cannot
authenticate captures or landmark identity. Report fields always retain:

- both_captures_independently_authenticated: false
- original_gameplay_physics_verified: false
- automatic_collision_export_permitted: false

The prior eight-category manual evidence gate remains mandatory before
original collision surfaces could be used in the Nintendo Switch engine.
No gameplay/runtime code is modified by this stage.
