# Stage245 — process-tree cleanup and inherited output pipe closure

## Risk

Stage244 capped bytes written to the host log, but the main emulator process
could exit while a child process retained the inherited stdout/stderr pipe.
The drain thread would then wait for EOF after the parent exit. Merely killing
or reaping the parent would not guarantee that the pipe closes.

## Changes

- Add an explicit best-effort process-tree termination helper.
- POSIX runners start in their own session; cleanup sends SIGKILL to the
  isolated process group, including descendants that inherited the pipe.
- Windows cleanup invokes `taskkill /T /F` without a shell and records its
  return code. This is best-effort; it is not a Windows Job Object guarantee.
- When the runner times out, terminate the isolated tree before waiting for
  the output drain.
- When the parent exits but output remains open for two seconds, attempt tree
  cleanup and wait again. Any run that required process-tree cleanup after the parent exited is
  not accepted as a clean Stage231 collection, even if the pipe eventually
  closes. If the pipe still does not close, mark the drain incomplete and
  block collection.
- Record cleanup attempted/success/method/error in the private launch report.

## Evidence

A fake host runner spawns a 60-second child that inherits stdout, then exits
with code 0. The test confirms the output pipe remains open after the parent
exit, cleanup is invoked, and the drain reaches EOF. Dedicated CI exports a
small JSON report made from temporary synthetic processes only.

## Boundaries and follow-up

- No original game files or genuine captures are used in this CI.
- This is host process management, not evidence of guest execution or GPU
  rendering.
- POSIX process-group cleanup is directly exercised on Ubuntu CI. Windows
  `taskkill` cleanup is a best-effort fallback; a Job Object implementation
  would provide stronger descendant ownership on Windows.
- Stage241 remains the latest verified deko3d NRO. Authentic GPU execution
  and original iOS visual parity remain unverified.
