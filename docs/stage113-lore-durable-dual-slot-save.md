# Stage 113 — experimental durable game progress across Switch NRO exits

The Stage112 fictional Level1-1 mechanics lab ran on **real NeXium
guest AArch64 CPU instructions**: [four successful jobs in run
#39603358966](https://github.com/stanmasked/he-man-remake/actions/runs/39603358966),
including real NPAD buttons, 12 `frame_rx` screenshots, opened gate,
both lore rewards and byte-identical save/reset/load frames. However,
the Stage108 96-byte receipt was held only in RAM. Exiting homebrew
lost the save.

Stage113 adds an **entirely optional, non-iOS** persistence layer.

## Player-visible controls (test NRO only)

- Existing L/R are unchanged, still RAM-only.
- **ZL** writes to SD using a two-slot redundant record. **ZR** loads
  the latest compatible undamaged record. An extra HUD rectangle on the
  right displays grey (no result), green (disk store passed), cyan
  (disk load passed), or red (disk operation failed).
- No filesystem operations occur at startup or from ordinary movement.
  Even on an emulator with no SD mount, failed ZL/ZR must leave current
  player/reward state intact and keep the game running.

The two files, if a writable SD mount exists, are named
`sdmc:/switch/heman_level11_lore_lab.0.bin` and
`sdmc:/switch/heman_level11_lore_lab.1.bin`.

Each **128-byte** file has 4-byte magic `HLD1`, a versioned 12-byte
header with monotonically increasing little-endian sequence number,
the existing canonical 96-byte Stage108 native player/reward snapshot,
a 64-bit FNV-1a accidental-corruption checksum, and eight zero reserved
bytes. Neither an original iOS asset nor native process pointers,
original source frame files, geometry, screenshots or purchase data
are stored.

A new write targets the **older/invalid slot** instead of overwriting
the most recent valid record. Cold-start loads inspect both files,
reject truncation, trailing bytes, checksum mismatch, wrong version,
incompatible world identity or invalid lore state, and choose the
highest-sequence compatible slot. If the newest file is interrupted
or corrupted, the older valid file can still restore the previous
progress. On any failure the player structure is not mutated.

### Exact safety and durability limitations

This design is **not guaranteed power-fail atomic on FAT/SD**.
`fwrite+fflush+fclose` reports ordinary I/O errors but cannot ensure
physical media flush or guarantee rollback under arbitrary block-level
corruption. A first interrupted save may be lost, and both slots may
be destroyed by SD card or filesystem failure. Never represent it as
a secure anti-cheat signature or an original iOS save format. A valid
FNV-1a digest is NOT evidence of authenticity; cross-level correctness
is checked separately by native session world/role seals.

The SD mount may be absent in a headless NeXium run; **no actual
Switch console SD persistence has yet been proven**. This build
adds a candidate implementation and real native-host filesystem
tests, while the existing Stage112 NeXium gameplay proof applies
only to the earlier RAM-save NRO.

## Verification

The host `native/tests/test_level11_durable_save.c` creates REAL
small files in an isolated Linux temporary directory and checks:
first-store, two independent slots, cold reinit and restore,
newer-slot corruption recovered from earlier good slot, truncated
and extra-byte records rejected, both slots damaged, unavailable
directory write, incompatible native world fingerprint refused,
invalid lore snapshot refused, and byte-for-byte no mutation
of player state on failed loads/writes.

```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
```

Dedicated GitHub Actions `level11-durable-save.yml` uses both
GCC/Clang ASan+UBSan and builds an actual updated AArch64 NRO via
devkitA64. This checks compilation, not real hardware/NeXium SD writes.
No genuine user IPA/game maps were opened or uploaded; the studio's
original source-fidelity gate [Issue #110](https://github.com/stanmasked/he-man-remake/issues/110)
remains OPEN. Stable two-room Switch release and verified three-room
NeXium build stay untouched.
