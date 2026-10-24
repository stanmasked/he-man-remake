# Stage253 — require a matching Stage252 preflight before real launch

## Purpose

Stage252 can determine whether the owner supplied plausible launch inputs, but
a report alone does not stop someone from launching Stage240 with different
files or arguments. Stage253 closes that gap: the Stage240 launcher now
requires a recent passing Stage252 report for every non-test launch and
revalidates the report against the current files, paths and argument template
before Stage231 creates a session or writes a nonce to the SD root.

## Gate contract

Stage253 rejects a launch unless all of the following hold:

- The report is a regular non-symlink UTF-8 JSON file no larger than 64 KiB.
- Schema is heman-stage252-runtime-preflight-v1, result is
  preflight_passed_not_launched, and the exact required check set is present
  with every check true.
- The operator-confirmed SD-root flag is true. The report still must say that
  the SD mapping was **not independently verified**.
- The normalized path fingerprints for the emulator, NRO, SD root, session
  directory and argument template match the exact invocation.
- Current emulator and NRO hashes match the preflight hashes; the current NRO
  still has an NRO0 header and valid size.
- The report is no older than 30 minutes and its timestamp is timezone-aware.
- The report is outside the SD tree and session directory; the SD root and
  session destination are still non-symlink paths, writable/fresh as required,
  and private on POSIX. Existing switch/heman-stage230 path components are
  rechecked as real directories so PREPARE cannot follow a symlinked output tree.

The gate adds the preflight report SHA-256, creation time, age, and matched
hashes to stage240_launch.json. This supports audit and troubleshooting; it
is not a signature or independent proof that the emulator configuration has
not changed.

## Owner-private usage

First run Stage252 with the exact emulator, NRO, mapped SD root, session path
and argument template that will be used for Stage240:

    python3 tools/stage252_runtime_preflight.py \
      --emulator /absolute/path/to/emulator \
      --nro /absolute/private/heman_deko_png_transfer.nro \
      --sd-root /absolute/path/to/actual-sdmc-root \
      --session-dir /absolute/private/stage253-run-001 \
      --confirm-sd-root-mapping \
      --output /absolute/private/stage252-preflight.json \
      -- --no-gui "{nro}"

Only if the report says preflight_passed_not_launched, pass that exact report
and the same paths/arguments to Stage240:

    python3 tools/stage240_private_emulator_launcher.py \
      --emulator /absolute/path/to/emulator \
      --nro /absolute/private/heman_deko_png_transfer.nro \
      --sd-root /absolute/path/to/actual-sdmc-root \
      --session-dir /absolute/private/stage253-run-001 \
      --preflight-report /absolute/private/stage252-preflight.json \
      --timeout 300 \
      -- --no-gui "{nro}"

The commands are templates. Adapt the argument vector to the installed
emulator's actual version. The NRO, paths and argument template must remain
unchanged between preflight and launch. If more than 30 minutes pass or any
input changes, rerun Stage252 and use a new report/session path.

The public CI fake runner is explicitly marked --test-only-runner and is the
only path allowed to bypass the Stage253 gate. That flag must never be used
for a real emulator.

## Validation and evidence boundary

Public CI tests matching, mismatch, stale, missing, oversized, symlinked and
tampered reports using synthetic fixtures. It never starts a real emulator and
never publishes original game resources or private host logs.

Stage253 can detect stale or mismatched inputs, but it cannot cryptographically
authenticate a JSON report, independently prove the SD mapping, establish
that the emulator is GPU-capable, or prove original iOS graphics parity. All
reports continue to keep GPU and original-iOS parity attestations false until
separate runtime evidence exists.
