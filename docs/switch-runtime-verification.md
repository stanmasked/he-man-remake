# Switch NRO runtime verification — synthetic He-Man probe

This checklist is for a **homebrew-capable Switch emulator or a console configured
to run homebrew**. It is not a guide for obtaining console keys or commercial
Nintendo firmware. Use software and assets you are permitted to use.

This repository builds an independent technical probe. It does **not** distribute
or run the original iOS IPA, its game media, or a complete He-Man remake.

## Evidence levels

1. **CI compilation:** devkitPro generates an AArch64 ELF and a valid NRO0
   file. It does not mean that execution has occurred.
2. **Application boot:** a compatible emulator/console displays the text
   header and `Synthetic boot self-check: PASS (180 scripted frames)`.
   Only a real runtime screen/log demonstrates this.
3. **Interaction:** a human or automated input driver verifies controls,
   simulated motion, attacks, and state changes.
4. **Original-game parity:** requires separate private comparisons with the
   user-owned IPA. Nothing in this checklist establishes such fidelity.

## Obtaining the current test build

- Open the **latest successful** workflow named
  `Nintendo Switch synthetic core probe (devkitPro)` on GitHub Actions.
- Verify the workflow's commit SHA matches the commit being tested.
- Download the `heman-synthetic-switch-core-probe` artifact from the run
  and extract `heman_core_probe.nro`. Artifacts are kept for seven days.
- Preserve the SHA-256 and byte count reported by the build log alongside
  the runtime evidence. Do not upload original iOS resources.

## Manual boot and controller checklist

- [ ] Launch the downloaded `.nro` using a homebrew-compatible environment.
- [ ] Confirm that the diagnostic line says `PASS`, with no failure code.
- [ ] Observe a text map with `@` (player), `#` (solid platform),
      `E` (patrolling synthetic enemy), `*` (pickup), `C`
      (checkpoint), `!` (hazard) and `>` (exit).
- [ ] Press Left/Right and confirm the player's x-coordinate changes; the
      camera should advance when moving far enough right.
- [ ] Press A, confirming vertical position/velocity changes then landing.
- [ ] Move close to the enemy, face it and press X. A successful hit changes
      enemy HP; a swing out of range or backwards must not.
- [ ] Approach the enemy and verify that the HP/contact-hit counters can
      change without losing all HP on a single frame.
- [ ] Press B and confirm core respawn plus restoration of initial enemy HP.
- [ ] Press Plus and verify the app closes normally.

## Failure handling

A startup error or a detected runtime error displays a **persistent diagnostic
screen** with core, boot-check and combat codes. Record these codes and a
screenshot; press Plus to leave. If the application exits or hangs without a
diagnostic, record the emulator/homebrew version, the exact NRO SHA-256, the
point of failure, and any app logs.

Do not report "emulator verified" based on an NRO header check, unit tests or
an unobserved CI artifact. This is an experimental text console driven by a
nominal 1/60-second simulation step and approximate sleeping; proper
real-time pacing, graphics, audio and original enemy AI remain unimplemented.
