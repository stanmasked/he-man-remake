# Stage256 — cross-platform capture safety

## Purpose

Stage255 introduced descriptor-relative PREPARE/COLLECT operations on POSIX
hosts that support O_DIRECTORY, O_NOFOLLOW, and dir_fd. The project must also
validate the Stage254 compatibility fallback used on platforms without those
features. Stage256 adds a three-platform CI matrix for the Stage231 session
and Stage243 bounded-evidence tests.

## Coverage

The matrix runs on Ubuntu, Windows, and macOS with Python 3.12:

- Stage231 session preparation, collection, NRO validation, and synthetic
  symlink/path-replacement regressions.
- Stage243 bounded reads and descriptor-relative reads when the platform
  exposes the required APIs.
- A synthetic capability summary records the actual platform and whether
  descriptor-relative I/O is available. Unsupported symlink operations are
  skipped only when the host refuses to create the test symlink.

No emulator, GPU, original game assets, IPA, firmware, keys, or private host
logs are used. Every summary keeps real-launch and GPU-attestation fields false.

## Security boundary

The POSIX descriptor mode is tested on Ubuntu and macOS when supported. The
Windows runner validates the compatibility path, not POSIX race-resistance
guarantees. Stage256 does not claim that the Windows fallback can pin a
directory inode against concurrent path replacement, nor that filesystem
checks can independently prove the emulator's actual SD mapping.

Stage253 remains mandatory for real Stage240 launches. A fresh owner-host
Stage252 report, explicit operator confirmation of the mapped SD root, private
evidence archiving, and independent runtime/GPU diagnostics are still required.

## Acceptance

Keep the Stage256 PR in Draft until all three OS jobs and the core CI matrix
pass. Archive each synthetic platform summary privately and verify each
downloaded copy by SHA-256.
