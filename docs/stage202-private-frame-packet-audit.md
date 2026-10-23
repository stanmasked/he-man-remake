# Stage202 — private single-Symbol packet audit

Stage202 extends the existing owner-local frame decoder with an opt-in packet-assembly check. Original IPA bytes, resource keys, byte offsets, per-Symbol fields, source crops and exact packet coordinates remain local; only aggregate validation flags are suitable for reports.

## Changes

- The strict single-Symbol parser now retains the full four-integer prefix and seven-integer tail in memory, alongside the six finite binary32 fields. These values are consumed only by the optional assembly path and are never added to the JSON report.
- The private decoder accepts `--assemble-packet`. When selected, it resolves the existing cut/texture/image chain, constructs the verified Symbol contract and UV metadata, and invokes the Stage201 CPU packet assembler for exactly one isolated Symbol.
- The isolated audit uses an identity SpritePlayer transform because the original runtime's per-player transform state is not serialized in this sequence record. It therefore validates Symbol-local geometry only; it does not claim complete scene composition.
- The report contains only counts and booleans: packet count, vertex count, UV-pair count, finite geometry, source-order preservation, winding-flag computation, and explicit false values for full-frame composition and original-runtime pixel parity.
- Packet assembly runs before writing the optional private crop, so an unresolved or unsupported field fails closed instead of producing a misleading success report.

## Local source check

The owner-held IPA was read locally from the user's Drive file, without copying it into GitHub. An independent local parse of one single-Symbol source frame confirmed exact record EOF, a unique cut handle, an in-bounds source rectangle, a power-of-two allocated texture extent, and finite CPU geometry with four XY vertices and four UV pairs.

That establishes a real source-data packet path, but not a full original render. The isolated SpritePlayer transform is identity, and no GPU sampling, filtering, blending, full-frame composition or original-runtime pixel parity is claimed. Private resource names, offsets, coordinates, image data and the IPA checksum are intentionally excluded from this repository.

## Regression coverage

Synthetic tests verify that the parser preserves the serialized Symbol fields needed for assembly, a valid synthetic Symbol produces exactly one finite packet summary, and unsupported tween identifiers fail closed. Existing crop, alias-resolution, exact-EOF and bounds tests remain in place.

## Next step

Run the opt-in audit locally against an owner-selected frame and compare the packet's transformed bounds against a trusted original-game capture or recorded gameplay frame. Only after that comparison should the project add any texture-sampling or GPU adapter work.
