# Stage193 — native Symbol color, tween, blend and mask contract

Stage193 resolves the first four floats and all seven scalar fields after the six-float block from the original iOS ARMv7 executable. This remains a reference-model stage: no original assets are copied into GitHub and no production renderer is modified.

## Serialized Symbol layout after the resource name

The original `Symbol::fileIn` stores the fields in this order:

1. Four signed 32-bit values: SpriteCut handle, rotation in degrees, local X offset, local Y offset. The three transform values are converted from integers to native float members.
2. Six IEEE-754 float values:
   - **alpha multiplier**
   - red multiplier
   - green multiplier
   - blue multiplier
   - independent X scale
   - independent Y scale
3. Seven signed 32-bit values:
   - easing selector for X/Y offsets
   - easing selector for rotation
   - easing selector for X/Y scale
   - easing selector shared by alpha/red/green/blue
   - raw source blend factor
   - encoded destination blend-factor ID
   - Symbol mask

This reconciles the serialized field count used by the existing strict sequence parser with the native in-memory field offsets. The first color float is **alpha**, not red: `SpritePlayer::updateMesh` applies it as a shared multiplier to the player's R/G/B/A values; the next three floats multiply the corresponding R/G/B channels. Resulting vertex channels are clamped to [0,1].

## Native interpolation evidence

`SpritePlayer::tween` calls the stored function pointers in four groups:

| Serialized easing field | Native members controlled |
|---|---|
| 1st | X and Y offsets |
| 2nd | rotation |
| 3rd | X and Y scale |
| 4th | alpha and RGB multipliers |

The original `EaseFunction::setFunction` accepts selector IDs 0–17 and dispatches to a function pointer. Across the private original census, no selector falls outside that range. The model preserves numeric IDs and group semantics; it does not substitute guessed easing formulas.

## Blend and mask behavior

- The source blend field is retained as a raw GL factor. The destination field is an encoded ID passed through `GLUtil::getGLBlendFunc`: IDs 0–7 map to `GL_ZERO`, `GL_ONE`, and six standard GL blend factors; an unsupported destination maps to -1.
- Either blend field equal to -1 disables the per-Symbol override. If both are present, the native painter applies the pair.
- The final scalar is a bit mask. Native paint skips a Symbol when `symbol_mask & active_player_mask` is nonzero.

## Private aggregate census

Across 14,971 Symbol references in each original resolution pack, the aggregate field patterns agree:

- Alpha: 857 zero values and 8 values above 1.0; values are clamped at render time.
- Red, green and blue: each has six zero values; the only RGB value above 1.0 is one blue multiplier.
- Easing selectors used by the source are limited to IDs 1, 2, 4 and 5. All four selector positions have been mapped to their respective tween groups.
- Source/destination blend pairs: 12,874 `(-1,-1)` (no override), 2,075 `(1,1)` (active `GL_ONE, GL_ONE`), 12 `(-1,1)` and 10 `(1,-1)`. The last 22 pairs are inactive because one side is the sentinel.
- Symbol mask values: 13,500 zero, 1,467 one, and four equal to 12.

No resource labels, per-record values, offsets, PNG bytes or private reports are committed.

## Implementation

Added `src/heman_tools/symbol_render_contract.py`:

- parses the four-int / six-float / seven-int contract into named fields;
- models alpha-first RGB multipliers and native output clamping;
- maps tween selector IDs to the verified offset/rotation/scale/color groups;
- models the asymmetrical blend encoding and sentinel behavior;
- implements the native mask-intersection suppression rule;
- rejects malformed lengths, booleans, non-finite floats, and out-of-range integer/selector values.

Added 20 asset-free synthetic tests for field order, color multiplication/clamping, selector groups, blend-factor mapping, sentinel pairs, mask behavior, and malformed input. These tests do not access the original IPA.

## Next steps

1. Resolve the remaining SpriteCut rectangles that still exceed the native power-of-two allocation and trace the native GL texture wrap/UV path before deciding whether those records are malformed or intentionally exceptional.
2. Use the now-named color/easing/scale fields in a private multi-symbol composition prototype, retaining source order and the existing fail-closed cut policy.
3. Compare a composed original frame privately against an authentic source render. No original-game visual parity is claimed yet.
