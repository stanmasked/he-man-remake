# Stage264 — Tile collision-shape field read/write envelope

## Purpose

Stage263 identified incoming call candidates from the collision map and tile map into the tile shape getter. Stage264 examines the origin of that getter's stored member by joining three selected functions in the original iOS Mach-O: Tile::fileIn, Tile::setCollisionShape and Tile::getCollisionShape.

A private Thumb disassembly found a candidate member at offset **44 bytes** from the Tile object base:

- Tile::fileIn initializes the candidate member to null and includes one direct BL candidate to Tile::setCollisionShape after reading serialized tile data.
- Tile::setCollisionShape writes a candidate handle into the same member offset after resource lookup logic.
- Tile::getCollisionShape reads that member and conditionally reads a nested pointer from the handle.
- The getter contains no obvious texture-alpha sampling or geometry calculation. This does not establish the type or origin of its stored reference.

This 44-byte offset is a machine-code member offset, not a serialized tileset-file offset or a physics-world coordinate. Exact method positions and original machine-code bytes remain private.

## Implementation

The Stage264 tool reads the user-held IPA in memory after the bounded iOS preflight. It resolves three Thumb-marked method intervals from Mach-O __TEXT,__text and nlist symbols. A constrained decoder recognizes 16-bit Thumb immediate-offset LDR/STR and the Thumb-2 BL pattern previously tested on fabricated input. The tool checks a common candidate field, nearby zero-initialization and an exact setter branch target.

All raw symbol names, original instruction bytes and method addresses are omitted from the report. Output is restricted to the ignored local_reports/ directory; the executable is never extracted for this tool.

## Evidence boundary

These findings support a tile-deserializer → setter → candidate member → getter static chain. They suggest that collision geometry may be referenced as a serialized resource and resolved into an object, rather than created within the getter from texture pixels. They do not independently establish object types, runtime reachability, alias correctness, alpha-channel irrelevance elsewhere, collision response or iOS gameplay parity.

## Public synthetic checks

The Stage264 workflow uses a wholly fabricated ARMv7 Mach-O, fictional tile symbols, invented Thumb machine instructions and ZIP fixtures. Its regression tests cover instruction decoding, exact BL target matching, missing setter call, missing null initialization, member mismatch, absent method symbol, fake IPA read-only semantics and output redaction.

## Next gate

Analyze the source string/reference resolution inside Tile::setCollisionShape and verify what type of resource it selects. Then inspect the handoff to CTileMap::initializeCollision. Do not import original collision masks into the Switch physics until the resource binding and response semantics are independently established.
