# Stage133 — TWO gameplay-origin guest saves, two generations, cold latest selection

This stage addresses a limit of Stage122: its second, different-progress
journal was created by a **host fixture editor**, not by gameplay. Here the
second 120-byte save is written entirely by the **unchanged Nintendo Switch
homebrew NRO** using its native libnx SD adapter and ZL+L chord.

A first genuine NeXium process navigates the synthetic Level1-1 lore lab,
earns both fictional collectibles, saves the completed state, and exits. The
independent host auditor verifies the actual 120-byte SD journal bytes.

In a **sixth independent NeXium process** (the intervening runs are
read-only fault experiments on separate sandbox clones):

1. The guest begins with empty RAM and receives *real pinned NeXium kernel*
   ZL+R input at frames 80–105, restoring the first original save.
2. The guest **moves right with real NPAD D-pad** at frames 180–215; its
   actual frame_rx image must visibly differ from the first saved location.
   The fictional collectibles and gate status remain unchanged.
3. A fresh ZL+L chord at frames 290–320 requests a **second native SD save**.
   The unchanged C99 journal writer must put generation (first + 1) into
   the previously unused second slot, with the same world binding and both
   collectible bits intact but a different player x.
4. The independent host-side secure dirfd auditor reads both actual slots
   by their 120-byte sizes and original SHA-256s. The original first journal
   must remain byte-for-byte untouched; the second must be valid and
   reproduce the new guest screenshot x within 1.1 game units.
   Screenshots at frames 265, 345 and 445 must confirm the moved
   character and stable saved scene, not a mere green HUD.

A **seventh independent NeXium process** starts with fresh empty RAM and
receives **only** ZL+R restore at frames 520–538. Its guest screenshot at
frame540 must match frame345 of the real second-save process, not frame485
of the first. Neither saved slot may have changed across the cold restore.
Both guest processes must have genuine CPU/SVC progress, pinned kernel
NPAD publication, complete logged frame_rx screenshots and clean exits.

### Evidence boundaries

- This is **real emulator-native gameplay write/read** of a deliberately
  fictional, asset-free homebrew tutorial. It is not an original iOS
  level, save format or game-accurate rendering.
- The gameplay difference is the actual protagonist position created by
  D-pad movement, not a host-side change to the SD journal bytes.
- Verifying libnx filesystem commits inside NeXium does not prove
  real Nintendo Switch flash durability or power-loss atomicity.
- CI publishes only guest PNGs, logs, hashes and metadata-only receipts.
  Never upload original IPA data, private user saves or raw journal bytes.
- The mock-only contract suite tests the *verifiers*, not the real guest.
  Only a completed GitHub Actions guest run can substantiate the claim.

Source is in `tools/verify_nexium_real_resave_generations.py`, with
`tests/test_nexium_real_resave_generations.py` and the opt-in
`HEMAN_LORE_RESTART_PHASE=resave` schedule.
