# Stage257 — private host evidence archive

## Purpose

Stage257 packages the results of a real Stage240 host attempt into a bounded,
private ZIP archive that can be copied to the project's private Google Drive
evidence area. It preserves the Stage252 preflight report, Stage240 launch
manifest, Stage231 session/collection outputs, and selected SD capture files.
It never copies the emulator executable or NRO binary.

## Safety checks

- Requires absolute paths to the Stage252 report, session directory, SD root,
  and output archive.
- Rejects symlinked or non-regular reports, session files, and capture files.
- Uses descriptor-relative reads when the host supports O_DIRECTORY,
  O_NOFOLLOW, and dir_fd; the compatibility fallback rechecks path components
  and is documented as weaker against concurrent replacement.
- Requires the Stage252 report and session/output directories to be owner-only
  on POSIX. Windows ACL privacy is not independently audited.
- Refuses output inside the SD root, session directory, or a Git worktree, and
  refuses to overwrite an existing archive.
- Bounds every included file and the final archive size. The archive contains
  a manifest with file sizes and SHA-256 hashes, but no absolute source paths.
- Validates that the Stage240 gate accepted the exact Stage252 report hash,
  that emulator/NRO hashes match across reports, and that the attempt did not
  use the test-only runner.
- Includes only a fixed whitelist of evidence files; original emulator/NRO
  binaries, ROMs, IPAs, firmware, and keys are never included.

## Evidence boundary

The archive records a host attempt and bounded files. It is not signed, does
not independently verify the emulator's SD mapping, and does not prove that
the guest executed or that a GPU generated the readback. All GPU capability,
runtime attestation, and original iOS parity fields remain false.

## Usage

After a real Stage240 attempt has produced the Stage252 report and session
manifests, choose a new archive filename in a private directory outside the
repository, SD root, and session directory. Invoke the tool with the four
required flags: --preflight-report, --session-dir, --sd-root, and --output.
The command prints the archive basename, byte count, SHA-256, and explicit
non-attestation flags. Upload the ZIP to private Google Drive, then download
it independently and compare SHA-256 before treating the transfer as verified.

## Validation

The Stage257 workflow runs synthetic tests on Ubuntu, Windows, and macOS. It
covers report-to-launch hash binding, rejection of test-only manifests,
symlink rejection, private destination rules, and ZIP manifest/hash contents.
No original assets or real emulator are used in public CI.
