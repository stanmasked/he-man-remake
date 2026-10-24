# Stage244 — bounded emulator output during execution

## Change

Stage243 bounded reads after the emulator process exited, but Stage240 still
redirected stdout/stderr directly to an unbounded file. A noisy or hostile
runner could fill the owner's disk before the later 4 MiB check.

Stage244 changes Stage240 to drain combined stdout/stderr through a pipe and
persist at most 4 MiB to the private `host-launch.log`. After reaching the
cap, the reader continues draining and discards excess bytes so the child
does not block on a full pipe. The manifest records retained bytes, observed
bytes, configured limit, truncation state, and drain errors.

If output was truncated or the drain did not complete, Stage231 collection is
skipped and the attempt cannot be marked as a complete bundle. The truncated
log remains useful for diagnostics but is not represented as complete evidence.
The existing timeout and nonzero-exit reporting remain separate.

## Validation

The dedicated source-only CI launches an invented Python child that emits
4 MiB + 12,345 bytes. It asserts that the reader observes all emitted bytes,
retains exactly 4 MiB, reports truncation and never writes a larger log. The
Stage240 unit test exercises the full launcher path with a fake runner that
emits more than the cap; this is not a GPU execution.

## Boundaries

- The output file is capped at 4 MiB during process execution, not merely
  checked after exit.
- The pipe reader uses fixed-size chunks and bounded storage.
- Genuine Switch/GPU execution and original iOS visual parity remain
  unverified.
- On platforms where an emulator spawns descendants that inherit stdout,
  a stuck pipe drain is recorded as incomplete and blocks collection; process
  tree termination beyond the main runner remains a separate portability
  consideration.
- Raw runtime captures and logs stay in the owner's private Google Drive
  Evidence Archive. CI contains only invented source-only test results.
