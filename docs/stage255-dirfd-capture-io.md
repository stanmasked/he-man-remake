# Stage255 — descriptor-relative capture I/O

## Purpose

Stage254 rejected symlinked SD directory components when they were present at
the time of each check. Stage255 strengthens the supported POSIX path by
opening the SD root, switch, heman-stage230, and session output directory
and then performing guest-file I/O relative to the resulting directory file
descriptors. A later replacement of a checked pathname therefore does not
redirect an already-open descriptor to a different directory.

## Changes

- Stage231 PREPARE opens the SD capture chain one component at a time using
  O_DIRECTORY | O_NOFOLLOW and dir_fd; missing child directories are
  created relative to their already-open parent.
- Stale-file removal, nonce creation, and nonce rename are performed relative
  to the pinned capture-directory descriptor.
- The session manifest is created relative to a pinned output-directory
  descriptor with exclusive creation, refusing pre-existing entries.
- Stage231 COLLECT opens the same capture chain and session directory, reads
  the manifest/nonce/RGBA/receipt by basename relative to those descriptors,
  and refuses symlinks or non-regular files.
- Collected output files are exclusively created relative to the pinned
  session directory; a second concurrent collection fails closed at the
  output creation/manifest marker.
- Stage243 adds read_limited_at, a size-bounded, no-follow reader for a
  pinned directory descriptor. NRO hashing now opens the final NRO component
  without following a symlink and validates the opened descriptor and size.
- Regression tests replace switch with a symlink after the directory is
  opened, then verify PREPARE and COLLECT continue using the originally
  opened directory rather than the replacement target.

## Portability and security boundary

Descriptor-relative mode is enabled only when the platform exposes
dir_fd, O_DIRECTORY, and O_NOFOLLOW support. Other platforms retain the
Stage254 path-checking fallback for compatibility; that fallback cannot make
the same race-resistance claim. The SD-root pathname's ancestors are still
resolved by the operating system when the root itself is opened, and these
checks cannot independently prove which SD device the emulator maps. They
also do not prevent a process with sufficient access from modifying the
contents of the same already-open directory inode.

Stage253 remains mandatory for every real Stage240 launch. A fresh owner-host
Stage252 report, explicit confirmation of the emulator's actual SD mapping,
private evidence storage, and independent runtime/GPU diagnostics are still
required. No synthetic test is evidence of a real emulator launch, GPU
execution, or original iOS graphics parity.

## Validation

The Stage255 workflow uses temporary synthetic files only. It runs Stage231,
Stage243, Stage240, Stage252, and Stage253 regression tests and emits a
synthetic-only summary. Public CI must not contain original game resources,
private host logs, ROMs, IPAs, firmware, or keys.
