# Development roadmap

- [x] Confirm level metadata exists in a privately held original IPA.
- [x] Analyze and document preliminary `.lvl` headers.
- [x] Write conservative metadata reader and synthetic unit tests.
- [x] Confirm boundaries of counted object records in all 39 iOS v2.0.0 maps.
- [x] Decode object names, states, 3×3 transforms, and four typed property formats.
- [x] Decode named point groups and indexed references in all 39 trailers.
- [x] Decode v1–v3 multilayer tilemaps with 213/214 file validation and distinguish the named collision layer.
- [ ] Identify collision tile semantics and match shape ownership and object relationships.
- [x] Decode local-space .shape polygons and circles, with 409/409 private archive validation and synthetic tests.
- [x] Implement an asset-free SVG schematic viewer for local level coordinates.
- [x] Implement experimental per-pixel collision-mask readout and deterministic host-only landing/jump prototype (approximation, not original physics).
- [x] Prototype static full-body wall/ceiling collisions and bounded slope adhesion (not authentic iOS physics).
- [ ] Verify actual tile semantics, one-way platforms, hitbox dimensions and original movement constants.
- [ ] Match primitive .shape resources and original player hitbox to level objects.
- [x] Implement and headlessly test a keyboard-controllable host physics scene with camera, jump and reset.
- [x] Add independent synthetic pickup/checkpoint/hazard/exit event state and deterministic headless replay.
- [x] Display synthetic event markers and a camera-aware HUD in the desktop demo, with headless CLI parity.
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
- [ ] Boot the synthetic NRO in a Switch emulator or homebrew-enabled console and confirm controller input/console lifecycle.
- [ ] Document differences from iOS v2.0.0.

No original IPA or extracted copyrighted resource may be committed, uploaded as Actions artifact, or placed in a public GitHub issue.
