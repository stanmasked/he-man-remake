# Stage 113 — opt-in dual-slot saves surviving cold launches

The opt-in fictional Level 1-1 mechanics lab has already been proven to
run under the pinned NeXium guest: [Stage112 full success](https://github.com/stanmasked/he-man-remake/actions/runs/39603358966).
Previous **L and R** save/load operated only in RAM and disappeared when
the application exited. Stage113 introduces a small, independent C99
persistent journal and an **explicit SD-only chord**, without modifying
either the 96-byte in-memory snapshot format or the old real guest route.

## Console controls and output

The optional Nintendo Switch lab NRO (`switch_lore/`) now supports:

- **L / R**: unchanged, tested in NeXium, in-RAM save/load.
- **ZL+L**: first take the same valid RAM snapshot, then *attempt* to
  write its 96-byte payload into one 120-byte journal record on SD.
- **ZL+R**: attempt to restore the newest valid compatible journal
  into an independently initialized live game session, then update
  the in-RAM save. Bad/missing files leave the live session untouched.
- The rectangle at the right of the existing HUD shows **green** on a
  successful SD operation, **red** on a failed/unavailable operation,
  **grey** before SD access. No SD mount is attempted at boot or on
  ordinary in-RAM L/R. No auto-load or user-save override occurs.
- SD location: `sdmc:/switch/heman_lore_lab/progress0.bin` and
  `sdmc:/switch/heman_lore_lab/progress1.bin` (two distinct slots).
  Original commercial files are NEVER read or written.

## Why two files?

`native/src/heman_level11_journal.c` is platform-independent C99;
it accepts a strict slot read/write callback. Its **canonical little
endian 120-byte** envelope includes version, monotonic generation, the
existing canonical 96-byte lab snapshot and FNV-1a accidental corruption
detection (NOT a cryptographic signature).

Before every store, the module checks both candidate slots *including*
inner world/event binding compatibility, chooses the **older, missing or
damaged slot**, and never writes the last valid one. On load it chooses
the newest fully compatible candidate, falling back to the preceding
good slot after truncation, corruption or interrupted overwrite. It
rejects version drift, invalid game geometry, invalid reward state,
malformed file length, generation overflow and missing I/O callbacks,
without changing the current session on error.

## Reproducible automated checks

The dedicated GCC and Clang ASan/UBSan test suite exercises a real
C99 fictional world and an in-memory journal that can fail halfway
through a write. The same test binary is then executed in **four
different host processes**, with actual disk files used for write,
cold-read, second write, second cold-read; an appended byte corrupts
the newest slot, and a **fifth process** must recover the older one.
It cannot pass by accidentally retaining game state in process RAM. The same workflow also appends an extra byte to the newest file and then truncates that file to 60 bytes; each time a fresh process must reject the newest record and recover the previous complete slot.

The actual Switch NRO is separately cross-compiled through the
existing `switch-lore-lab.yml` devkitPro workflow, checking its NRO
header and AArch64 ISA. Its **ZL+L/ZL+R SD operations are not claimed to
have run under NeXium or on real Switch hardware** unless a separate
host/device runtime test genuinely exercises `fsdevMountSdmc`, mkdir,
file I/O and filesystem flush.

This is **best-effort torn-write recovery, NOT guaranteed physical
power-loss atomicity**, nor a transactional Switch user SaveData
service. A sudden power loss or platform cache behavior is not covered
by host tests. Failure of SD mounting falls back safely to RAM. The
original iOS persistence model is unknown. No original game assets,
level geometry or IPA bytes were added, and [Issue #110](https://github.com/stanmasked/he-man-remake/issues/110)
remains open for source-authentic Level1-1 reconstruction.
