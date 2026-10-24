# Stage246 — Windows Job Object ownership of emulator descendants

## Problem

Stage245 uses a POSIX process group on Linux/macOS and a best-effort
`taskkill /T /F` fallback on Windows. The Windows fallback is weaker: process
tree enumeration can race with descendants and does not provide the same
kernel-managed lifetime boundary.

## Implementation

- Add a Windows-only `WindowsJobObject` wrapper using the Win32 Job Object
  API.
- Set `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, assign the launched process, and
  keep the Job Object handle open for the duration of the run.
- On parent exit, query `JobObjectBasicAccountingInformation`. If any
  descendants remain, close the Job Object to terminate the assigned tree,
  record that cleanup was required, and refuse to treat the run as clean
  Stage231 evidence.
- If the process count cannot be queried, close the Job Object fail-closed
  and record an error rather than accepting a clean run.
- If timeout or an inherited output pipe requires cleanup, close the Job
  Object and wait for the bounded output drain to reach EOF.
- Keep `taskkill` only as a fallback for callers that have no Job Object.
  Normal Stage240 Windows launch is fail-closed if Job Object creation or
  assignment fails.

## Validation

The Windows-only CI launches an invented parent process. The parent waits
until it has been assigned to a Job Object, then starts a 60-second child
which inherits stdout and exits. The test verifies that the parent has exited,
the descendant keeps the pipe open, the Job Object reports active processes,
closing the Job Object succeeds, and the output drain then reaches EOF.

The report is synthetic host-process evidence only. It does not attest NRO
execution, deko3d/GPU readback, or parity with the original iOS game.

## Portability boundary

The test runs on a Windows GitHub Actions runner. Job Object assignment may
be refused by a restrictive enclosing job or host policy; Stage240 fails
closed rather than launching an unmanaged process tree. The process is
assigned immediately after Popen returns, so there is a narrow interval
before assignment; the dedicated test synchronizes its child spawn to ensure
the tested descendant is created after assignment. A future hardened launcher
could create the process suspended and assign it before first instruction,
but Python's standard Popen API does not expose a stable public suspended
thread handle for that sequence.
