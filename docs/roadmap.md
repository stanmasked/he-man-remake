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
- [x] Build a standalone platform-neutral C99 host core proof-of-concept, with native GCC/Clang test cases.
- [ ] Compare Python and C gameplay traces; add alpha collision slopes and a real platform backend.
- [ ] Introduce a Nintendo Switch homebrew build target and emulator smoke tests.
- [ ] Document differences from iOS v2.0.0.

No original IPA or extracted copyrighted resource may be committed, uploaded as Actions artifact, or placed in a public GitHub issue.
