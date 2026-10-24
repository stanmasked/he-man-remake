# Stage262 — bounded Thumb-2 direct-call candidate census

## Purpose

Stage261 established that the original iOS Mach-O contains symbol-table entries defined in the executable text section, but a symbol name is not a call relationship. Stage262 scans five selected Thumb-marked functions for the **specific Thumb-2 BL instruction encoding** and resolves its decoded target address to an exact text-defined symbol-table entry. The output is an aggregate, not a source-code reconstruction or a runtime trace.

## Original IPA: owner-private aggregate observations

The targeted private analysis found the following Thumb BL candidate sites, with exact matches to text-defined symbols:

| Selected function role | BL candidate sites | Exact text-symbol targets |
| --- | ---: | ---: |
| Shape-to-physics bridge | 9 | 9 |
| Collision event handler | 6 | 6 |
| World-entity bounding-shape query | 2 | 2 |
| Tile bounding-shape query | 0 | 0 |
| Shape resource loader | 10 | 10 |
| **Total** | **27** | **27** |

Inside the shape-to-physics bridge, candidate call targets include shape geometry getters and a Box2D polygon-shape setter. The event handler includes candidate calls to game-message argument/dispatch methods. The shape-resource loader includes reads of typed values and string data. These statements derive from *direct static instruction candidates with exact symbol-address targets*, not only textual co-occurrence.

They establish a more specific lead for reconstructing the loader-to-physics chain, but **do not prove call-site reachability**, runtime execution, the specific collision source of Level 1-1, or any gameplay collision response. An ordinary linear sweep over a bounded symbol interval is not a full instruction decoder or control-flow graph.

## Run privately

From the repository root, with the user-owned IPA stored off-repository:

```sh
PYTHONPATH=src python -m heman_tools.thumb_bl_call_census \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/stage262-thumb-bl-direct-calls.json
```

The selected IPA entry is loaded in memory after the existing IPA security preflight. The report contains only anchor-role labels, code-length estimates and target *category counts*; it contains no original raw symbol names, executable bytes, machine-code offsets, disassembly or original asset contents.

## Public regression contract

CI uses a fictional ARMv7 Mach-O, fabricated Thumb functions and fabricated text-defined symbols. Tests cover forward/backward BL targets, BLX exclusion, distinct defined-target classification, targets without exact matches, missing anchors, invalid section bounds, private path enforcement and non-export of raw names.

The workflow is read-only and never loads the real IPA.

## Remaining blockers

The following are **not** established:

- whether any observed call site can execute in Level 1-1;
- whether candidate shape loaders create the bodies used for level collision;
- whether alpha masks are supplied to Box2D or to a different collision system;
- physical response, slope rules, one-way surfaces, sensors and hazards;
- comparison with actual original iOS gameplay;
- permission to import collision masks automatically into the Switch version.

**Next stage:** validate a bounded code/reference path around resource-to-body construction, with separate classifications for a syntactic direct branch, a verified function boundary and an observed execution trace.
