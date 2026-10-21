# Stage122 — two valid generations with DIFFERENT visible game progress

The preceding stages used actual guest-produced synthetic Level1-1 lore-lab
save bytes. Stage119 verified restore from an older intact journal when a
newer envelope had been truncated, but the intended two snapshots contained
the **same** gameplay state. Stage122 tests a more discriminating case:
**two structurally valid journal records with different collected-lore
progress**, and a genuinely new NeXium process choosing the later generation.

## Exact host fixture generation

After the first unchanged Switch NRO has really completed its path and
the Stage116 descriptor-relative audit confirmed its 120-byte SD record,
the Stage122 fixture builder:

1. Reads the original 120 bytes through the source-root anchored
   `read_confined_sd_slot_bytes` with `O_NOFOLLOW`, strict size, a pinned
   leaf descriptor and the original SHA-256 from the guest receipt.
2. Copies this genuinely guest-produced, fully earned 2-collectible snapshot
   into slot0 in a brand-new, isolated CI `NEXIUM_DATA_ROOT`.
3. Derives a second **host-synthesized** later-generation record from those
   exact source bytes, altering only the fictional Bio state: clear the
   player's Bio picked-bit and lore Bio flag, reducing the lore counter
   from 2 to 1 while preserving the Art pickup, wall-crusher upgrade, gate
   trigger, position and world seal. Recompute the inner and outer FNV-1a
   integrity checksums, and increment its generation by exactly 1.
4. Independently confirm **both** slots are structurally valid, retain the
   same game-world bindings, have divergent collectible counts (2 vs 1),
   and rank slot1 as the latest generation. Unchanged source files are
   never overwritten.

FNV-1a is an accidental-error detector, **not** cryptographic provenance.
The new slot is a **synthetic modification, not a second genuine gameplay
save**. The real NRO's native loader must independently check whether it is
compatible with the exact running world.

## Fifth independent real guest process

The same unchanged Switch NRO is launched in a **new** pinned NeXium
`debug_boot` process and given only the four actual kernel NPAD events
ZL, ZL+R, ZL, release. The guest must start with no collected lore and
must remain unchanged up to its pre-load frame 518.

At frame 540, the oracle requires a **green** SD load result with:
upgrade on, gate open, Bio off, Art collected, RAM-save indicator on,
and exactly **one** lore item — not the two-item source state. A
successful restore from slot0 instead of slot1 is therefore a failure.
The hero's saved x coordinate must match the original source frame 485.

Frame_rx RGB pixels must differ from the source full-progress saved
frame, but they must also be identical when masking **only**
the fictional Bio HUD lamp, Bio pickup sprite, lore count bar, and
diagnostic SD result indicator. Any unrelated changes fail the test.
No real PNG file is overwritten: masking occurs in memory during hashing.

The final independent read-only SD audit requires two intact journal hashes,
both unchanged after the guest restoration, and a later-generation slot1.

## Limits and privacy

This is a test of native *selection priority* using guest execution and
synthetically differentiated snapshots. It is **not** evidence that the
player genuinely collected a different set of items in a second save,
that the original iOS game's save layout is compatible, or that real
Nintendo Switch flash storage survives an actual abrupt power cut.

All guest save bytes remain inside the runner's private CI workspace.
Only metadata, hashes, actual source-generated guest screenshots and
logs are uploaded. No original iOS assets or ROMs are added.
