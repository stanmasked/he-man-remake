# Level trailing point groups: Stage 004

Read-only reverse engineering from the privately supplied iOS v2.0.0 archive, with no original game bytes in this public repository.

After the **counted object records** comes an unsigned 32-bit little-endian `group_count`. Each group is:

- `u16` UTF-16LE code-unit length; that many UTF-16LE code units for `name`.
- `u32` point count.
- For each point: `u32 marker` (unknown meaning), `f32 x`, `f32 y`, `f32 z`, `u16 short_field` (unknown meaning), `u32 link_count`, followed by `link_count` little-endian `u32` local point indices.

The point entry therefore occupies **22 + 4 × link_count bytes**. Duplicate links are preserved; they may have meaning in the original format. Do not assume these indices represent movement edges, nor that named points imply collidable geometry. Names like camera and checkpoint suggest roles, but runtime behaviour remains unverified.

## Local verification (private, not committed)

- 39 of 39 level trailers decoded exactly to end-of-file, without unparsed trailing bytes.
- 427 named groups, 1,061 points, 134 index references, 95 distinct group names.
- All point coordinates were finite, all indices within their own group's point-count bounds.
- Both unknown numeric fields were zero for the 1,061 points in this input. The parser preserves arbitrary values for compatibility.
- All corresponding `.lvl` files from `screen-med` and `screen-xlarge` were byte-identical. This does not imply graphics have identical resolution.

Use with a local original IPA:

```sh
PYTHONPATH=src python -m heman_tools.waypoints_cli --ipa /private/He-Man-v2.0.0.ipa --level MULevel1-1.lvl --out local_reports/level1_points.json
PYTHONPATH=src python -m unittest discover -s tests -v
```

**Never upload** reports, copies of game assets or the original IPA to GitHub. This research parser is not an emulator, not a full level renderer, and not a Switch build.
