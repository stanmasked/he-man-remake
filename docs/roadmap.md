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
- [ ] Reconstruct ground tile collisions, and match primitive shape resources to level objects.
- [ ] Build and test gameplay systems (movement, camera, combat) on host fixtures.
- [ ] Introduce a Nintendo Switch homebrew build target and emulator smoke tests.
- [ ] Document differences from iOS v2.0.0.

No original IPA or extracted copyrighted resource may be committed, uploaded as Actions artifact, or placed in a public GitHub issue.
