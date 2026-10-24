# Stage263 — incoming Thumb BL call-site evidence

## Why the direction matters

Stage262 decoded *outgoing* candidate Thumb-2 BL sites inside five selected functions. Stage263 scans the bounded executable text region for **incoming** BL encodings whose calculated target equals one of those same functions. It assigns candidate source sites to the nearest preceding defined text symbol. This is an approximate static caller classification, not a verified instruction-reachability graph.

## Owner-private results

The original ARMv7 iOS executable produced 47 selected incoming BL candidates:

| Target role | Candidate inbound BL sites | Distinct nearest named caller entries |
|---|---:|---:|
| Shape-to-physics bridge | 41 | 19 |
| Collision event handler | 0 | 0 |
| World entity shape query | 3 | 3 |
| Tile shape query | 3 | 2 |
| Shape resource loader | 0 | 0 |

The 41 candidate direct calls to the shape-to-physics bridge mostly originate from combat and attack-state functions. Of the three calls to the tile collision-shape query, **two** occur in the tile-map collision-initialization function and **one** occurs in a collision-map constructor. The latter path is a more relevant investigative lead for the first level than the combat-oriented Shape2D-to-Box2D bridge.

**Absence of a direct BL site is not absence of a runtime call.** Virtual dispatch, register-indirect branches, ARM-state calls, BLX and dynamically determined functions are outside the scope of this decoder.

## Public pipeline

The analyzer performs bounded string/symbol table parsing, resolves exact named branch targets, and produces only aggregate categories and generic target-role labels. It reads the user-held IPA in memory; all detailed evidence remains in the ignored local-report directory and private Drive. Public CI uses a fake ARMv7 Mach-O, fabricated symbol names and fabricated branch encodings. No original executable, symbol names or addresses are placed into public artifacts.

## Evidence boundary

A candidate BL encoding plus exact target symbol address is meaningful static evidence, but it does not establish that this instruction is actually reached on a particular gameplay path. Assigning the closest preceding symbol is an approximate interval heuristic, not a complete function boundary reconstruction.

Neither Stage262 nor Stage263 has yet proven Level 1-1 resources reach the tile-collision initialization, that tile alpha determines solidness, or that the Switch prototype matches iOS gameplay. **Native collision import remains unauthorized.**

## Next investigation

Independently inspect the original CollisionMap/CTileMap initialization path and determine whether it queries tile geometry from atlas data, texture alpha, or some other source. Capture the evidence separately from experimental collision physics.
