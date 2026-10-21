# Development roadmap

- [x] Confirm level metadata exists in a privately held original IPA.
- [x] Analyze and document preliminary `.lvl` headers.
- [x] Write conservative metadata reader and synthetic unit tests.
- [x] Confirm boundaries of counted object records in all 39 iOS v2.0.0 maps.
- [x] Decode object names, states, 3×3 transforms, and four typed property formats.
- [x] Decode named point groups and indexed references in all 39 trailers.
- [x] Decode v1–v3 multilayer tilemaps with 213/214 file validation and distinguish the named collision layer.
- [x] Privately count original iOS Level1-1 object-table entries (159), three .map layers over 300×19 tiles and occupancy totals (map 1579, collision 790, destructible 33) in both screen packs; see [Stage138](stage138-original-level1-structural-readiness.md). These are structural counts, **not** original collision behavior.
- [x] Add asset-free, aggregate-only private readiness gate combining selected level+map byte parity, explicit map-file links, collision occupancy topology, full object parsing and named-point links; no original coordinates or classified collision semantics exported.
- [ ] Identify collision tile semantics and match shape ownership and object relationships.
- [x] Decode local-space .shape polygons and circles, with 409/409 private archive validation and synthetic tests.
- [x] Implement an asset-free SVG schematic viewer for local level coordinates.
- [x] Implement experimental per-pixel collision-mask readout and deterministic host-only landing/jump prototype (approximation, not original physics).
- [x] Prototype static full-body wall/ceiling collisions and bounded slope adhesion (not authentic iOS physics).
- [x] Compare candidate first-level coordinate envelopes privately: **142/159** object translations lie within the origin-zero 300×19×32 serialized tile extent (only **3/159** within direct cell indices); this is a *hypothesis*, not verified world scale. Privately compare **409** paired identical global `.shape` files and **94** embedded references; none directly match level object identities. See [Stage139](stage139-private-level1-coordinate-shape-evidence.md).
- [ ] Verify actual tile semantics, one-way platforms, hitbox dimensions and original movement constants.
- [x] Audit owner-private global shape references in **81** physics-structure resources: **71** contain at least one exact length-prefixed UTF-16 shape identifier, with **137** resource/shape candidates and **112** unique shape stems; **400/409** shapes appear in the source geometry registry metadata. This is lexical evidence only; see [Stage140](stage140-private-physics-shape-lexical-census.md).
- [x] Bound and parse repeated source physics-record *envelopes* for **81/81** private `.ps2d` / `.pstruct2d` files: **187 records**, **187 UTF-16 string references**, **175** matching shape identifiers; leave 50-byte per-record fields and 13 nonempty trailers opaque. See [Stage141](stage141-physics-record-envelope.md). No original asset bytes or automatic hitbox claims.
- [x] Stage142 source-private analysis: **187** opaque 50-byte blocks contain **139** unique patterns; **13** additional trailers declare **44** groups, while all 13 admit merely *candidate* initial UTF-16 labels. No trailer group/parameter semantics decoded; see [Stage142](stage142-opaque-physics-trailer-evidence.md).
- [x] Stage143 synthetic-only candidate framing for nonempty physics trailers: compare bounded [UTF-16 label][N opaque bytes] and [N opaque bytes][UTF-16 label] repeated layouts, require exact EOF, detect ambiguous fits and explicitly mark single-group matches inconclusive; see [Stage143](stage143-physics-tail-boundary-hypotheses.md). **No real original trailer boundaries confirmed**.
- [ ] Match primitive .shape resources and original player hitbox to level objects.
- [x] Implement and headlessly test a keyboard-controllable host physics scene with camera, jump and reset.
- [x] Add independent synthetic pickup/checkpoint/hazard/exit event state and deterministic headless replay.
- [x] Display synthetic event markers and a camera-aware HUD in the desktop demo, with headless CLI parity.
- [x] Add one-time synthetic health restoration for pickups through atomic session state; verify cap, reset semantics and rollback with host/Switch startup checks.
- [ ] Investigate authentic iOS event scripts; never assume synthetic rules match original behavior.
- [ ] Add enemies, combat, real camera logic and animation from original game data.
- [x] Prototype one synthetic patrolling enemy, X-button melee attack, HP and invulnerability in independent C99 code (NOT reverse-engineered iOS combat).
- [x] Build a standalone platform-neutral C99 host core proof-of-concept, with native GCC/Clang test cases.
- [x] Compare 720 C99/Python synthetic frame states and 32 packed slope-mask columns.
- [x] Implement separate C99 packed-mask actor walking and jumping experiment.
- [x] Route optional packed pixel masks into the main C99 `hm_step` game-loop; compare a 26-frame synthetic incline trace.
- [x] Reduce repeated full-mask validation to once per native simulation frame, and benchmark on a synthetic 300x19 map.
- [x] Add a portable atomic session adapter and native tests for deterministic physics+combat transitions and rollback.
- [x] Synchronize combat and player state on automatic synthetic hazard/fall respawns, with rollback regression.
- [x] Add deterministic, one-frame-delayed player defeat respawn to the synthetic combat session with input validation and atomic rollback tests.
- [ ] Profile the C99 engine on Nintendo Switch hardware/emulator, and compare real-game mechanics privately.
- [x] Add a libnx-independent, host-tested 40x20 ASCII tile viewport and synthetic pickup/checkpoint/hazard/exit markers for the Switch probe (not an original sprite renderer).
- [ ] Introduce a production graphics/input adapter with textures and real-time pacing for future Switch builds.
- [x] Add first opt-in libnx/devkitA64 **console probe** build recipe (unverified cross-compilation).
- [x] Cross-compile the synthetic text-console Switch probe to a structurally valid NRO with devkitPro in GitHub Actions.
- [x] Add an identical GCC/Clang + libnx source-level 180-frame synthetic startup self-check with console PASS/error reporting.
- [x] Add a second source-identical host/Switch boot self-check covering combined movement, hazard respawn, combat defeat and atomic rollback.
- [x] Add controller-triggered deterministic 180-frame runtime replay with a shared GCC/Clang/Switch fingerprint and nonmutating live-state contract.
- [x] Boot independently authored synthetic Switch NROs in **NeXium** and verify genuine guest framebuffer and controller input (not physical Nintendo Switch proof). See [PR #54](https://github.com/stanmasked/he-man-remake/pull/54).
- [x] Audit **private iOS v2.0.0** file pairing between medium and extra-large screen packs: all 39 level files identical, 213/214 ordinary .map files identical plus one distinct exceptional sky map. Local-only aggregate gate in [Stage137](stage137-private-ios-screen-pack-parity.md); no original level geometry or assets uploaded.
- [ ] Document differences from iOS v2.0.0.

No original IPA or extracted copyrighted resource may be committed, uploaded as Actions artifact, or placed in a public GitHub issue.

- [x] Add a separate synthetic 640x360 libnx software-framebuffer NRO with a portable host-tested parallax/tile/player/enemy scene (not original game assets).
- [x] Confirm asset-free 640x360 raster NRO execution and actual controller-driven RGBA HUD updates in **NeXium**, including checkpoint recovery and two X victories; **hardware remains untested**. See [PR #54](https://github.com/stanmasked/he-man-remake/pull/54).

## Verification milestone — 20 October 2026

- [x] Confirm first checkpoint death and **next-frame native recovery** using exact guest NeXium input logs and genuine HUD screenshots: [PR #50](https://github.com/stanmasked/he-man-remake/pull/50).
- [x] Require strict full-line HID press/release identity so held buttons cannot impersonate released buttons: [PR #51](https://github.com/stanmasked/he-man-remake/pull/51).
- [x] Prove first **two-X** sword victory after natural checkpoint death with original guest PNG HP 2→1→0: [PR #52](https://github.com/stanmasked/he-man-remake/pull/52).
- [x] Validate B/manual replay after victory through original C99 engine and both native compilers: [PR #53](https://github.com/stanmasked/he-man-remake/pull/53).
- [x] Prove real NeXium **B-retry then second two-X victory** using authentic emulated framebuffer captures: [PR #54](https://github.com/stanmasked/he-man-remake/pull/54).
- [x] Draw independent **CLEAR** HUD only after native `HM_EXIT` completion and test source RGBA pixels under GCC/Clang; all prior NeXium regressions green: [PR #55](https://github.com/stanmasked/he-man-remake/pull/55).
- [x] Confirm **genuine NeXium guest PNG** evidence for native `HM_EXIT` and CLEAR after real D-pad movement: [PR #57](https://github.com/stanmasked/he-man-remake/pull/57), [successful run #39339811505](https://github.com/stanmasked/he-man-remake/actions/runs/39339811505). Marker world-X progresses 125.5→185.5→265.5→369.5 px and remains stationary after release; source-authored CLEAR is absent before input and present at frames 60/80/120/300. The exact head passed 15/15 workflows.
- [ ] Replace synthetic world geometry with *private* verified level/collision reconstruction from user's own IPA, without committing extracted commercial resources.
- [ ] Reproduce original iOS gameplay rules (enemy AI, damage, level triggers, camera, physics) based on private comparative traces rather than synthetic assumptions.
- [ ] Implement real content pipeline, animation, sound, menu, save/continue and complete multi-level campaign.
- [ ] Test stable frame pacing, memory, handheld/docked input and rendering on Nintendo Switch hardware; verify real-game parity privately.

**Status boundary:** Successful NeXium NRO proofs establish that the independent synthetic prototype boots and responds to inputs. They **do not establish** a playable remake of the original commercial iOS game. Never publish IPA bytes, extracted assets or private reports to GitHub.
