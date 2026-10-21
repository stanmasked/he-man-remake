# Stage135 — exhaustive 120-byte virtual SD journal interruption matrix

This stage provides a **host-only, asset-free** test matrix against the
experimental C99 journal's portable on-disk format. It does not modify any
Switch NRO, original iOS assets, stored SD saves or runtime emulator code.

The test first generates two intentionally different synthetic records:
- Old slot0: generation 17, valid 120-byte record at fictional player x=24.
- New slot1: generation 18, valid 120-byte record at fictional player x=51
  with recomputed inner and outer FNV-1a checksums.

It asserts that a complete second record ranks after the first. It then
systematically tests:

1. **All 120 incomplete write lengths (0 through 119):** each truncated
   newer record must be rejected as `wrong_length`; only generation 17
   is an eligible structural restore candidate.
2. **A flipped bit at each of all 120 byte offsets:** a single changed bit
   anywhere in the fully written newer record must make the outer envelope
   invalid or otherwise fail structural decoding. The older valid record
   must be the only remaining candidate.
3. **Trailing garbage:** adding 1, 8 or 120 bytes is not a valid atomic
   journal write; the older generation remains selectable.
4. **Outer checksum repaired after inner corruption:** corrupt the inner
   snapshot and update the outer envelope checksum; the independent inner
   checksum must still reject that new record.
5. **Two valid records with conflicting world seals:** the offline auditor
   must mark the world binding ambiguous, rather than invent compatibility
   with an unavailable live guest world.

The original synthetic older record must retain its byte-for-byte contents
and SHA-256 on every iteration. The matrix samples **over 240 different
new-record failure states**, not 240 host processes. Existing
`test_switch_sd_journal_audit.py` and real guest stages remain distinct.

These are structural tests of accidental corruption. FNV-1a is not a
cryptographic authentication mechanism. This test is not a simulated
physical power interruption, an `fsdevCommitDevice` durability guarantee,
a guest C99 loader execution, original iOS save compatibility or a
Nintendo Switch hardware test.

The more demanding [Stage134 PR #134](https://github.com/stanmasked/he-man-remake/pull/134)
continues to require actual NeXium guest PNG and SD receipts to demonstrate
fallback between two genuinely gameplay-written states after a separately
synthesized torn record.
