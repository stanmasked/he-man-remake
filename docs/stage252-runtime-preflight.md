# Stage252 — read-only runtime prerequisite preflight

## Purpose

Stage251 classifies backend claims after a host process exits. Stage252 moves
one step earlier: it provides a read-only preflight for the actual inputs
needed by Stage240, so a private attempt can fail before launching when the
emulator, NRO, SD-root path, session destination or command template is invalid.

## Owner-private invocation

Use this only on the owner-controlled host where the emulator and its real
mapped SD directory are installed. Adapt emulator flags to that exact build:

    python3 tools/stage252_runtime_preflight.py \
      --emulator /absolute/path/to/emulator \
      --nro /absolute/private/heman_deko_png_transfer.nro \
      --sd-root /absolute/path/to/actual-sdmc-root \
      --session-dir /absolute/private/stage252-run-001 \
      --confirm-sd-root-mapping \
      --output /absolute/private/stage252-preflight.json \
      -- --no-gui "{nro}"

The placeholder must appear exactly once as a standalone argument. The command
above is a template, not a universal emulator command. Check the installed
emulator's own help before using its flags.

The --confirm-sd-root-mapping option is an explicit operator assertion:
the operator has checked the emulator configuration and confirmed that this
exact path maps to its sdmc:/ root. The tool cannot independently prove that
mapping from filesystem metadata. Without this assertion the report remains
blocked.

## What is checked

- Emulator: absolute existing regular non-symlink file, executable permission,
  SHA-256.
- NRO: absolute existing regular non-symlink file, 20 bytes to 16 MiB, NRO0
  magic at offset 16, SHA-256.
- SD root: existing non-symlink directory, writable/searchable by the current
  user, and explicit operator confirmation of the mapping.
- Session output: fresh empty directory or a new child of a writable owner-
  private parent; rejects symlinked paths and group/world POSIX permissions.
  Python's standard library does not independently audit Windows ACLs, so the
  report says so rather than claiming ACL verification.
- Path separation: rejects output nesting inside the SD tree and session paths
  that contain or overlap the emulator/NRO.
- Launch arguments: bounded list, no empty/NUL arguments, exactly one standalone
  {nro} placeholder.

The tool does not launch the emulator, create the session directory, write to
the SD root, or modify input files. It prints a JSON report and optionally
writes it to a caller-selected absolute path outside the SD/session tree.
Only basenames and hashes are retained in the report, not absolute host paths.

## Evidence boundary

A passing result is named preflight_passed_not_launched. It means only that
local path checks passed and the operator confirmed the SD-root mapping. It
does not prove that the emulator will start, that the guest NRO will execute,
or that a GPU is used. These fields remain false:

- sd_root_mapping_independently_verified
- emulator_was_launched
- runtime_gpu_execution_attested
- gpu_capability_independently_verified
- original_ios_graphics_parity_attested

Public CI creates a synthetic executable and synthetic NRO only, runs unit
tests, and stores a synthetic preflight report. Never put original IPA data,
Nintendo firmware/keys, private logs or raw captures into public CI.

## Acceptance and next step

Stage252 is accepted when the unit tests and synthetic-only workflow pass.
A real preflight report must be generated on the owner-controlled host, archived
privately with its SHA-256, and reviewed before Stage240 is invoked. Keep the
real host log, session nonce, NRO hash, SD readback and reports in the private
Evidence Archive, then independently download and hash-check archived copies.
