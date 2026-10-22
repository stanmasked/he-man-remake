# Stage183 — isolated real-time Switch clock probe

Stage183 adds a second NRO dedicated to measuring a real libnx monotonic counter. The existing deterministic sprite-clock NRO, its fabricated callback schedule, and its exact-pixel verifier are not modified.

## Implementation

- Read the launch-relative monotonic timeline from `armGetSystemTick()` and convert counter deltas using `armTicksToNs()`. Display `armGetSystemTickFreq()` as diagnostic evidence.
- Feed monotonic nanosecond samples to the Stage182 portable bridge, then pass its capped millisecond delta to the existing 16-ms app-tick scheduler and synthetic sprite clock.
- During startup, skip clock sampling over actual 500-ms and 200-ms `svcSleepThread` calls. Each measured counter interval must be at least the requested sleep duration; each resumed dispatch must report 66 ms, schedule four updates, and retain a 2-ms accumulator remainder.
- Immediately sample the same timestamp again and require zero elapsed milliseconds, proving that the resumed callback refreshed the clock baseline.
- Sleep for 16 ms with the player clock paused: the scheduler must still consume one to four updates without changing player time. Then reactivate the player clock and require normal animation updates to resume.
- Interactive A toggles the app-level gate (no sampling while disabled); X pauses only the player clock; B resets; Plus exits.

## Verification sequence

1. GCC/Clang host checks for the Stage182 bridge remain separate.
2. The dedicated devkitPro workflow cross-compiles the new NRO and verifies its AArch64 ELF and `NRO0` header.
3. The same workflow downloads the built NRO, builds a temporary checkout of pinned NeXium, and executes the guest with framebuffer capture enabled.
4. The runtime job checks CPU/SVC/frame progress and requires OCR to detect STARTUP, COUNTER, RESUME and PASS in at least one late guest PNG, with no FAIL marker. Logs, screenshots and the OCR report are uploaded even when a check fails.
5. Do not replace or make the deterministic exact-frame oracle depend on this real-time probe; host/emulator scheduling jitter is expected.

## Evidence boundary

This stage measures the Switch/libnx guest counter and sleep behavior only. It does not establish original iOS timing parity, original game animation timing, or a production gameplay loop. No IPA, disassembly, original artwork, extracted resources, or private reports are included.
