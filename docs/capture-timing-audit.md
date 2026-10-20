# Stage 079 — private frame-timestamp and input-schedule audit

This stage adds a **read-only metadata checker**, not a video decoder.
The original iOS game's native frame rate and input latency have NOT
been measured. The 60 Hz protocol from Stage 077 is **provisional**.
A 60 Hz failure can mean that the hypothesis is wrong, not that the iOS
game is broken.

## Private JSON input

Place a paired timing JSON in ignored `local_reports/`:

```json
{
  "scenario_id": "landing",
  "nominal_fps": 60,
  "reference": {
    "platform": "ios",
    "capture_id": "private-ios-capture-001",
    "evidence_kind": "manual_observation",
    "clock_kind": "capture_monotonic",
    "frames": [
      {
        "script_tick": 0,
        "source_frame_index": 100,
        "timestamp_us": 12000000,
        "control": {"horizontal": 0, "jump": false}
      }
    ]
  },
  "candidate": {
    "platform": "switch",
    "capture_id": "private-switch-capture-001",
    "evidence_kind": "manual_observation",
    "clock_kind": "capture_monotonic",
    "frames": []
  }
}
```

**This example is intentionally incomplete**. A valid audit requires the
complete frame schedule from `contact_scenarios.scripted_controls` for
both platforms: 120–150 contiguous `script_tick` records, matching logical
inputs, independently obtained capture timestamps, and monotonically
nondecreasing decoded `source_frame_index` numbers. Real capture tooling
must supply this data; the checker does not invent it.

## Checks

- Enforce the five existing Stage 077 scenario scripts and exact frame count.
- Require per-frame timestamps in integer microseconds from a stated
  `capture_monotonic` clock; reject duplicate/reversed timestamps.
- Detect skipped or repeated source frame indices.
- Measure maximum interval deviation from 1/60 second (default 3 ms).
- Measure cumulative duration drift (default 6 ms).
- Normalize each stream to its **own first timestamp** and compare relative
  elapsed time (default maximum discrepancy 4 ms).
- Output only counts, thresholds and aggregate timing errors. No raw
  timestamp arrays, images, input events or original video are exported.

Run locally:

```sh
PYTHONPATH=src python -m heman_tools.capture_timing_audit \
  --timing local_reports/private-paired-timing.json \
  --out local_reports/private-timing-summary.json \
  --max-interval-jitter-ms 3 \
  --max-elapsed-skew-ms 4 \
  --max-duration-error-ms 6

PYTHONPATH=src python -m unittest discover -s tests -v
```

**Crucial limitation:** subtracting each capture's initial timestamp
makes constant inter-device offsets **undetectable**. Even a clean numeric
report cannot authenticate the origin of frame timestamps, verify frame
content, camera units, controller-to-image latency or real iOS behavior.
The tool must not be used as evidence of absolute cross-device
synchronization. Recorded footage and input logs must be checked
independently and kept private. An `evidence_kind` label of
`manual_observation` is a declaration, never an authenticated fact.

The source-only GitHub CI contains 19 entirely synthetic clock fixtures.
No commercial IPA, original gameplay trace, real video, screen coordinates
or source-derived timing report is committed.

All reports retain these false gates:

- `absolute_cross_device_time_offset_verified`
- `source_frame_timestamps_authenticated`
- `ios_gameplay_recording_authenticated`
- `original_gameplay_physics_verified`
- `automatic_collision_export_permitted`

The eight-category manual evidence gate still applies. No Switch physics
or raster runtime code is modified.
