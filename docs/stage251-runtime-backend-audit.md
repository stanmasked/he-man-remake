# Stage251 — bounded runtime backend log audit

## Purpose

Stage240 can launch an explicitly supplied emulator executable, but neither the
executable name nor a successful host exit proves which graphics backend was
actually selected. Stage251 adds a small post-run log classifier so the next
private runtime attempt can distinguish explicit API claims, software-renderer
indicators, conflicting claims, and missing evidence.

## Input and output

Run the tool only against a caller-selected runtime log:

    python3 tools/stage251_runtime_backend_audit.py \
      --log /absolute/private/path/emulator.log \
      --output /absolute/private/path/stage251_backend_audit.json

The log must be an existing absolute regular file, not a symbolic link, and is
bounded to 4 MiB. The report stores the input basename, byte count, SHA-256,
recognized backend labels, and line numbers. It does not copy raw log lines
into the report.

Recognized API claims include Vulkan, OpenGL, Direct3D 11/12 and Metal.
Software indicators include llvmpipe, lavapipe, SwiftShader, softpipe, swrast,
and explicit software/CPU renderer declarations. An API claim plus a software
indicator is classified as software-rendering evidence. Multiple API claims
are treated as ambiguous; no backend is guessed when no known marker appears.

## Stage240 launcher integration

The Stage240 private launcher now includes the audit result in
`stage240_launch.json` under `runtime_backend_log_audit`, with a separate
`runtime_backend_log_audit_status`. A complete, untruncated host log is
classified automatically after process output has drained. If the log was
truncated, unavailable, or could not be read safely, the report records a
skipped/failed status rather than classifying a partial log as complete.
This integration does not alter Stage231/236 collection acceptance.

## Evidence boundary

This is a **log classifier, not an emulator validator**. Runtime logs may be
incomplete, misleading or fabricated. A Vulkan/OpenGL line does not prove a
physical GPU is used; software drivers can expose those APIs. Therefore every
report sets all of these to false:

- \`gpu_capability_independently_verified\`
- \`runtime_gpu_execution_attested\`
- \`original_ios_graphics_parity_attested\`

A positive classification means only that a supplied log contains one
recognized graphics API claim and no recognized software-rendering marker.
It must not be promoted to a hardware-GPU success or used as a substitute for
independent runtime observation.

## Validation and storage

Public CI uses only a synthetic log and tests positive, negative, ambiguous,
oversized, relative-path and symlink cases. The workflow artifact contains the
synthetic JSON report only. Never upload original IPA resources, Nintendo
firmware/keys, private emulator logs or raw captures to public CI.

For a real attempt, retain the original log and its Stage251 report in the
owner-private Google Drive Evidence Archive. Record the NRO SHA-256 and link
the report to the same private session; independently download and verify
the archived report and its digest. Stage251 does not perform the runtime
launch and cannot resolve the missing local emulator/SD-root prerequisites by
itself.
