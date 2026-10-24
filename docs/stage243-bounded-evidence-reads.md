# Stage243 — bounded private GPU evidence reads

## Concrete risks closed

Stage231 COLLECT checked runner-log size but then separately read and copied
the source file. A log changing after the check could grow past its bound.
Stage236's inventory read every optional capture/log into memory without a
size limit; a malformed multi-gigabyte file could consume host memory and
prevent useful diagnostics of otherwise valid captures.

Stage243 introduces a common bounded reader:

- Opens only regular input files and refuses symlinks when O_NOFOLLOW exists.
- Rejects files exceeding configured maximum before full reading.
- Reads no more than maximum+1 bytes to catch growth between metadata
  inspection and read, without processing the entire expanded file.
- Stage231 COLLECT uses validated snapshots for private copy, instead of
  another unbounded copy of changing source files.
- Stage236 returns an "oversized" inventory status for invalid evidence
  and keeps valid companion capture analysis available.

Explicit limits: RGBA upload/render 512 bytes each; receipt and phase
256 bytes each; guest exit 128 bytes; nonce and host exit status 64 bytes;
session and collected JSON 64 KiB each; runtime log 4 MiB.

Stage240 currently redirects subprocess output to a private file, and
Stage243 does not make that file growth bounded during the subprocess's
execution; Stage243 bounds its subsequent reads/validation only. The
separate launcher log-writing policy requires a follow-up for resource
exhaustion under noisy/hostile emulators. Do not claim otherwise.

## Synthetic test evidence

The Stage243 host tests create sparse files one byte above the configured
limits, test missing/directory/symlink cases and validate that Stage231
fails closed. Stage236 reports oversized files without losing valid image
diagnostics, including malformed receipt/guest exit/nonce and oversized
optional collected JSON and logs.

A dedicated source-only six-case JSON matrix is included in CI.
Its output does not contain original artwork, private raw captures, or any
proof of GPU execution.

## Archive and acceptance boundary

Source-only CI and derived synthetic JSON can be published in GitHub and
copied to owner-private Google Drive Evidence Archive with SHA-256 and
ZIP CRC checks. Original IPA, extracted commercial game data, actual SD
captures and device/emulator logs remain owner-private. This stage does
not modify the Stage241 compiled NRO or DKSH.

All reports continue to mark authentic GPU execution and original iOS
visual parity **unverified**.
