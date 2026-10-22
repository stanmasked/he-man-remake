# Stage186 — native sprite-selection contract

Stage186 is a narrow reverse-engineering and test stage. The owner-held iOS v2.0.0 executable was inspected locally; no executable bytes, disassembly listings, original resource keys, asset data, or per-record source data are committed.

## Native control-flow findings

The following behaviors are supported by the executable's named ARMv7 methods:

1. `CSprite::customHandleMsg` has a message path that reads a string parameter and calls `CSprite::changeSequence`.
2. `CSprite::changeSequence` resolves a `SpriteSequence` resource by key, installs it in `SpritePlayer`, starts playback, and may reset the player to the first frame according to the component flag.
3. `CDirectionalSprite::customHandleMsg` has a separate message path that reads an integer selector, stores it, and invokes `updateSprite`.
4. `CDirectionalSprite::updateSprite` chooses among four preloaded sequence-resource slots in this selector order: selector 0 → storage slot 0; selector 1 → storage slot 1; selector 2 → storage slot 3; selector 3 → storage slot 2.
5. An invalid selector or an empty selected slot clears the active sequence. The native path does not fall back to another slot. When the selected slot has a resource, it is installed and playback starts.
6. `CPlayerCharacterHeMan::changeSprite` switches which directional-sprite component is active. This is a component-selection operation, distinct from selecting a sequence inside that component.
7. The generic `CPlayerCharacterState::onEnterState` dispatches to the state-specific virtual entry callback. The sampled He-Man idle callback resets friction, jump counter and force-idle state; it does not itself choose a sequence.

These findings show two distinct animation-selection paths: a named-sequence command and a four-slot directional selector. They do **not** yet prove which gameplay state/message selects each real He-Man sequence.

## Asset-free reference model

Added `src/heman_tools/sprite_selection_contract.py`. It models the four-slot selector with synthetic keys only and preserves the native fail-closed behavior:

- exact four-slot input;
- native selector order `[0, 1, 3, 2]`;
- no fallback if the selector is invalid or its chosen slot is absent;
- playback starts only when the chosen slot has a resource key;
- the reset-to-first-frame flag is kept independent of whether the chosen slot is populated.

The model is an executable contract for later integration, not a production renderer or a claim of original visual parity.

## Tests and validation

`tests/test_sprite_selection_contract.py` adds 14 synthetic-only tests for all four selector mappings, invalid selectors, missing selected/nonselected slots, reset behavior, malformed slot arrays, empty keys and strict input types.

CI validates the committed test/model pair on the current PR head. The owner-private source analysis is not run in public CI, and the original IPA is not included in the repository or workflow artifacts.

## Remaining work

- Trace the real message senders and state-specific callbacks to establish the gameplay-state → selector/message → sequence-resource mapping.
- Resolve the single unmatched Symbol handle and the resolution-specific handle differences recorded in Stage185.
- Reconcile SpriteCut rectangles outside raw PNG IHDR bounds with runtime texture dimensions/padding.
- Integrate only after the selection and texture-coordinate contracts have independent tests; then verify the original frame in NeXium.
