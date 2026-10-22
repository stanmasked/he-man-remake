# Stage188 — fail-closed directional sequence resolver

Stage188 adds an asset-free resolver between the serialized alias-to-sequence-pair data audited in Stage187 and the later renderer integration.

## Resolver contract

Given a sequence alias, a component variant, and an east/west direction, the resolver:

- Selects the matching resource key only from the requested variant.
- Uses the east or west key from that alias's pair.
- Returns `missing` if the requested alias is not present in that variant.
- Returns `ambiguous` if the alias was flagged by the census or appears more than once for that variant.
- Never falls back to another variant or silently chooses one of multiple candidate pairs.
- Rejects malformed entries, invalid variants, and invalid directions.

This resolver is deliberately separate from the four-slot `CDirectionalSprite` selector documented in Stage186. The relationship between the C++ selector value, the directional pair, and the message sent by each gameplay state is still a separate integration problem.

## Changes

- Added `src/heman_tools/directional_sequence_resolver.py`.
- Added 13 synthetic-only tests using fabricated aliases and resource keys.
- No original alias names, sequence resource keys, images, IPA data, or private reports are included.
- The helper is a reference model; it is not yet wired into the production NRO.

## Validation boundary

The model can resolve a supplied alias/variant/direction tuple deterministically. It does not establish which gameplay state emits the alias, does not render a frame, and does not claim visual parity. The next stage should trace the state handle and message path, then bind the verified resolver to the native sprite selection layer.
