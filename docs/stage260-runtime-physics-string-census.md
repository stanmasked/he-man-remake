# Stage260 — static runtime physics identifier census

## Goal

Stage259 described the alpha masks referenced by the collision atlas. Stage260 adds a separate, read-only census of printable identifiers embedded in the original iOS executable. The intent is to establish a second evidence source: the executable contains strings that look like physics, sensor, platform, tile-map, shape-format and collision-manager identifiers, as well as collision/sensor message identifiers.

The private analysis found distinct candidate-name counts in these categories: 9 physics type-name candidates, 4 sensor type-name candidates, 3 platform type-name candidates, 2 tile-map type-name candidates, 6 physics-format type-name candidates, 5 collision-manager type-name candidates, and 5 collision/sensor message identifiers. The full string inventory and executable hash remain private; the report publishes category counts and presence flags only.

## Method

The tool validates the IPA and thin 32-bit Mach-O header, reads the executable entry in memory, and counts unique printable ASCII runs from 5 through 512 bytes. It discards overlong runs, does not extract the executable, and never returns raw string values. Its local JSON output is restricted to ignored `local_reports/`.

The category counts are candidate string evidence only. They are not a decompiler result, a control-flow trace, proof that a method executes, or proof that a resource is attached to a physical body.

## Public tests

The workflow builds a fictional Mach-O header and fabricated strings. It verifies category counting, deduplication, overlong-string rejection, report redaction, IPA safety checks and private-output path enforcement. The workflow never loads the owner-held IPA or original assets.

## Interpretation boundary

Static identifiers strengthen the hypothesis that the executable contains a physics and collision subsystem. They do not establish that alpha pixels are used as collision geometry, nor do they prove solidness, slope rules, one-way surfaces, damage behavior, object ownership, transforms, collision response or iOS gameplay parity.

## Next gate

Use a separate, owner-private control-flow / cross-resource investigation to connect these static identifier candidates to an observed loader or call path. Keep any literal strings, original executable hash, object names and geometry details out of public artifacts. Do not import collision masks into Switch gameplay until runtime semantics are independently established.
