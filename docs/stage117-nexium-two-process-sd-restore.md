# Stage117 — restore one emulator SD journal across two NeXium OS processes

This is a **test-only** extension of Stage114–116. The first, unchanged
homebrew NRO executes the complete synthetic lore route, obtains an optical
`ZL+L` save and `ZL+R` restoration, and leaves a valid 120-byte
`progress{0,1}.bin` under the **isolated** CI `NEXIUM_DATA_ROOT`.

Only after that process exits with status 0 does the workflow start a **new**
NeXium `debug_boot` process with the exact same NRO and SD directory.
The second process starts from fresh game RAM. With
`HEMAN_LORE_RESTART_PHASE=restore`, the patched *temporary emulator*
runner injects **only** the guest NPAD transitions
`(520,ZL), (530,ZL+R), (535,ZL), (538,release)`. No movement,
upgrade, reset, RAM save, or SD save is permitted in the new process.
The NRO itself is not modified by the instrumentation.

The fail-closed evidence checks demand:

1. The first process completed a real guest restore plus independent valid
   virtual SD file receipt. The first save-scene image is frame 485.
2. The second runner truly completed and retired guest CPU cycles and SVCs;
   its kernel NPAD traces must publish the four restore-only transitions.
3. The second process genuinely starts with an empty lore state and no SD
   result. Its pre-restore frame 518 must still match its initial frame 30.
4. Its post-restore frame 540 must show success and match the *normalized
   genuine guest pixel digest* from first-process frame 485. Only the
   visual-only SD-result indicator is excluded from the pixel digest.
5. Stage116's descriptor-relative read-only receipt validates the same
   journal slot metadata and SHA-256 hashes **after** the second process;
   this makes accidental additional writes or re-saves a failure.
6. All raw saves remain within CI and are never uploaded to GitHub.
   Uploaded evidence is limited to logs, generated guest PNGs, hashes and
   metadata-only JSON reports.

This demonstrates restore after separate emulator host process execution
**only once a real Actions run passes**. A green mock-only regression suite
or queued guest job cannot establish the runtime result.

Out of scope: fsdevCommitDevice durability on genuine hardware, power loss
atomicity, concurrent hostile host modifications, original iOS gameplay
fidelity, and distribution of original proprietary assets. Follow
[He-Man runtime acceptance #123](https://github.com/stanmasked/he-man-remake/issues/123)
and [NeXium FS/FSP #42](https://github.com/stanmasked/nexium-macos-intel/issues/42)
for those remaining limits.
