# Stage121 — descriptor-anchored reads for test-only virtual SD fixture generation

Stage116 already enforces read-only virtual SD file auditing using
`O_DIRECTORY | O_NOFOLLOW` directory-fd traversals from `/`, with pinned
ancestors, regular file checks and exact 120-byte decoding.

The test-only Stage118 and Stage119 *fixture generators* previously made a
secure structural audit, but then reopened the source saved journal by
`Path.read_bytes()`. A malicious host could replace a symlink/path component
between inspection and fixture generation. Even though CI uses an isolated
virtual SD root, these separate host reads were inconsistent with the
security model and could copy unexpected bytes.

Stage121 introduces `read_confined_sd_slot_bytes(data_root, slot, expected_sha256)`:

- Only absolute paths with no parent traversal, slot 0 or 1, and lowercase
  64-hex-character expected SHA-256 are accepted.
- Every ancestor and `sdmc/switch/heman_lore_lab` component is opened
  relative to a previously pinned directory descriptor with `O_NOFOLLOW`
  and `O_DIRECTORY`. Descriptors remain open until the source bytes have
  been consumed.
- The chosen fixed-name source leaf uses descriptor-relative
  `O_NOFOLLOW | O_NONBLOCK`. FIFOs and other special files, aliases with
  `st_nlink != 1`, symlinks and oversized/truncated journals are rejected.
- Exactly 120 bytes must pass the existing *structural*, not cryptographic,
  journal decoder; then the SHA-256 must match the independently recorded
  original SD receipt.
- The caller receives bytes only inside CI memory; the raw bytes are never
  logged or uploaded.

Both the all-slots-corrupt fixture generator and the newest-truncated
fixture generator use this pinned, digest-bound read. No Switch guest
code, original iOS files, emulator kernel code or gameplay geometry changes.

Ten mock-only regression tests cover valid bytes, stale hash, parent
traversal, parent and leaf symlinks, hard links, FIFO, an adversarial
directory-rename/symlink swap after the original directory fd opens, and
a guard that rejects any use of `Path.read_bytes()` by either fixture
generator. A passing mock test is **not** a real guest NeXium result.

Limitations: directory-fd confinement in *host CI* is not evidence about
NeXium guest FS/FSP behavior, physical Switch SD durability, concurrent
host mount namespace attacks or real power-loss tolerance.
