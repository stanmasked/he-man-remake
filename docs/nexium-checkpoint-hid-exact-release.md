# Stage 051 — exact NeXium HID release log matching

Stage 049 (checkpoint activation + B reset) and Stage 050 (automatic defeat
and checkpoint respawn) require authentic **controller release** events in
NeXium's guest runner logs.

Previously the verifiers used substring matching for lines such as:

`HEMAN_CHECKPOINT_DEFEAT_HID frame=66 buttons=`

That fragment is also present at the beginning of the invalid, still-held
`HEMAN_CHECKPOINT_DEFEAT_HID frame=66 buttons=DRIGHT` record. A literal
substring check therefore could falsely confirm button release.

Both checkpoint guest verifiers now compare each complete HID event line,
including the entire `buttons=` state, to exact log lines from
`splitlines()`. This is independent of controller injection and
does **not** modify game logic, pinned upstream Rust code or frame capture.

Seven new source-only negative tests reject falsely claimed releases for
D-pad Right and B, a trailing `buttons= extra` suffix, an unrelated
prefix prepended to an otherwise correct HID event, and fake guest frame
capture records that occur only inside unrelated log text. Genuine capture
events must begin at the start of their own log lines. Existing valid traces
must remain accepted.

Only the Python image/log verifiers and Python test suites are changed.
Run source-only tests on Python 3.10/3.12/3.13 and the existing native CI.
These tests do not substitute for the real NeXium capture evidence provided
by Stage 049 and Stage 050.

No proprietary He-Man iOS data, Switch keys, firmware, compiled emulator
binaries or original commercial artwork are committed.
