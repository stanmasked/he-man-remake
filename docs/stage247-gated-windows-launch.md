# Stage247 — gated Windows launch removes the Job assignment race

## Problem

Stage246 assigned the Windows Job Object immediately after `Popen` returned.
The child could theoretically start running and create descendants before the
assignment completed. The test synchronized its child spawn, but production
startup still had a narrow unprotected interval.

## Implementation

On Windows, Stage240 now starts a small Python trampoline instead of starting
the emulator directly. The trampoline blocks reading its standard input and
cannot launch the emulator until it receives a serialized command followed by
a separate `GO` line.

The launcher:
1. creates the Job Object with `KILL_ON_JOB_CLOSE`;
2. starts the waiting trampoline with stdin/stdout pipes;
3. assigns the trampoline to the Job Object;
4. starts the bounded output-drain thread;
5. sends the command and opens the launch gate.

The trampoline then launches the actual emulator with `shell=False`, inherited
stdout/stderr, and stdin redirected from `DEVNULL`. Windows automatically
places the emulator and ordinary descendants in the same Job Object. Timeout,
pipe cleanup, and descendant checks continue to close the Job Object and
reject runs that needed cleanup. POSIX behavior remains unchanged.

The manifest now distinguishes `windows_gated_launcher_wrapper` from the
direct POSIX emulator process.

## Validation

Windows CI runs an invented target process which spawns a 60-second child
inheriting stdout, then exits. The wrapper is assigned to the Job before the
target command is sent. The test confirms the wrapper exits, the descendant
keeps the output pipe open, the Job Object reports an active process, closing
the Job Object succeeds, and the bounded drain reaches EOF.

This verifies host process ownership and sequencing only. It does not attest
the real emulator, guest NRO execution, GPU readback, or original iOS parity.

## Remaining limitations

- The trampoline uses the current Python interpreter as a small host-side
  launcher. If it cannot start, parse the command, or launch the emulator, it
  exits nonzero and the run is rejected.
- The Windows Job Object is assigned before the emulator process is created,
  closing the previous Popen-to-assignment race for the actual emulator.
- Job Object assignment can still fail under restrictive host policies; the
  launcher fails closed instead of running unmanaged.
