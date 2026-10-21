# Stage136 — actual native C99 SD-loader fallback matrix

Stage135 verified all 120 incomplete write lengths and all 960 individual
single-bit corruptions using the independent Python portable-file auditor.

Stage136 now tests the **actual C99 `hm_level11_journal_restore`** routine,
linked from the same native sources used to build the Switch lore-lab NRO.
The existing asset-free `native/tests/test_level11_journal.c` and
`native/run_tests.sh` are reused, so both GCC and Clang run this full
regression as part of the existing native CI workflow.

A real synthetic C99 session walks 30 physics ticks to collect the fictional
Art item and saves generation1. The same initialized native session unlocks
the fictional Wall Crusher and writes generation2, with a visibly different
native game state. Both authentic *native-writer* 120-byte snapshots and
world-binding checksums are retained in a private stack-resident memory IO
fixture. No iOS assets or user saves are involved.

The C99 test then:
1. Provides every possible **short-read length from 0 to 119 bytes** for
   the newer journal callback, while the previously valid older 120-byte
   slot remains available. The actual C99 loader must restore generation1
   with Wall Crusher off, retain the already-collected Art state and pass
   full session validation.
2. Restores the complete newer bytes and corrupts **every bit of all 120
   bytes**, one at a time (**960 unique one-bit faults**) without repairing
   the checksum. The same real C99 loader must choose generation1 on
   every attempt, leaving the original slot byte-for-byte untouched.
3. Restores the unmodified intact newer journal and demands generation2,
   the unlocked Wall Crusher and collected Art, proving the negative cases
   do not simply disable all newer saves.

All **1,080 primary fault variants** are deterministic in memory and
run inside a single host-native test binary, not 1,080 separate NeXium
processes. Existing independent-process tests with real filesystem files
remain intact and still exercise short writes, damaged bytes and fallback.

This adds real C99 journal-loader coverage to Stage135's Python structural
matrix; it does **not** attest NeXium emulated SD durability, physical power
interruption or Switch hardware, nor equivalence to any original iOS format.
The original Switch NRO source remains unchanged.
