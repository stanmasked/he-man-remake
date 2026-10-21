# Stage119 — restore older valid SD slot when newer slot is torn

This is a staged, **private test-only emulator** extension of
[Stage117](https://github.com/stanmasked/he-man-remake/pull/127) and
[Stage118](https://github.com/stanmasked/he-man-remake/pull/128).
It does not change the guest NRO, original iOS resources or libnx runtime.

The native C99 journal restore reads both slots independently, validates the
outer and inner checksums, verifies the live world/session, and selects the
highest-generation compatible journal. This scenario specifically tests the
**valid-older / truncated-newer** case with a genuine previously saved state.

The host test tool verifies an existing independent real guest SD receipt,
then copies the verified guest-produced 120-byte record into a fresh **CI-only**
virtual SD folder as slot 0. It constructs a *synthetic* next-generation journal
by changing only the generation and recomputing its outer FNV-1a checksum,
verifies that the complete candidate is structurally valid, and truncates it
to 64 bytes as slot 1. It confirms that the offline auditor accepts exactly
one older valid candidate and rejects the newer with `wrong_length`.

A **fourth independent host process** starts the identical NRO with fresh RAM
and the same restore-only ZL + R guest button schedule. The process may not
save, upgrade or move. The actual pinned NeXium kernel must publish all four
NPAD edges. Independent real frame_rx PNGs must show:

- An empty fresh game state before the load;
- A successful SD restore at frame 540;
- Gameplay pixels matching the saved frame 485 from the original process;
- Both SD slot byte counts and SHA-256 digests unchanged by the load attempt.

If the valid older journal is ignored, or if the truncated newer journal is
accepted, the CI check fails. The test also rejects false-green HUD-only
reports and missing/changed guest pixels. Separate mock-only regression tests
check bad source receipts, malicious extra input, false load failures,
unexpected slot mutation and generation overflow.

**What this is not:** It does not simulate an actual simultaneous hardware
power loss. The truncated next-generation record is synthesized in an isolated
directory, not produced by an interrupted physical SD write. It does not
demonstrate that newer and older slots contain different progression states:
the synthesized higher-generation record uses the same snapshot bytes.
It confirms old-slot recovery from a torn newer envelope, once the real guest
run completes.

Never point these tools at personal SD folders or publish raw save bytes.
CI artifacts include only metadata, hashes, logs and guest-generated images.
Real Nintendo Switch fsdevCommitDevice durability and power-loss recovery
remain separate acceptance tasks.
