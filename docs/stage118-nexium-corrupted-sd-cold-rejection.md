# Stage118 — real NeXium cold restore must reject checksum-corrupt journal

Stage117 checks a *positive* cold-process persistence scenario. This stacked
stage adds an isolated *negative* scenario, without altering the homebrew NRO.

After the first real guest successfully saves and the second independent
NeXium process successfully restores the same journal, a test-only host tool:

1. Inspects the first real SD disk receipt and verifies that the current
   source journal still has the same structural data and SHA-256 hashes.
2. Creates a brand-new `boot-evidence/fault-restart/nexium-data` sandbox,
   never overwriting the original run's virtual SD.
3. Copies only the verified **synthetic** 120-byte journal files into that
   isolated sandbox, flips one checksum-covered payload byte per valid slot,
   and confirms every resulting journal is independently invalid.
4. Runs a **third** NeXium OS process with the exact unmodified NRO and
   four restore-only real NPAD events: ZL, ZL+R, ZL, release.
5. Checks pinned kernel publication, CPU/SVC progress, 13 guest frame
   receipts, a fresh initial scene, an optical red SD failure indicator,
   unchanged game pixels, and unchanged corrupted journal hashes.

A green save/load indicator on malformed bytes fails CI. A failed load which
mutates the game also fails. The second, successful cold-restore sandbox is
not touched by the corruption test.

Only CI-generated metadata, hashes, logs and guest PNGs are uploaded. Raw
journal bytes, personal SD data and original iOS game assets must NEVER be
committed or uploaded. The fixture is test-only and must not be used on
personal SD folders.

**Provenance limits:** isolated guest emulator process success is not the
same as real Switch hardware, real flash power-loss atomicity, fsdevCommitDevice
durability, or original iOS fidelity. Neither this mock test nor a queued
Actions run is evidence of real runtime success. Only completed real NeXium
guest logs and genuine frame_rx PNGs qualify.

The primary acceptance issues remain
[He-Man #123](https://github.com/stanmasked/he-man-remake/issues/123)
and [NeXium FS/FSP #42](https://github.com/stanmasked/nexium-macos-intel/issues/42).
