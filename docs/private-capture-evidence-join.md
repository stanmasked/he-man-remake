# Stage 080 — join private media, timing and contact evidence

Stages 077–079 introduced independent capture records for five scenarios:
landing, jump, wall, ceiling and ledge. A numerical pass is insufficient
if it accidentally describes **another recording or capture session**.

This stage takes the original **private** JSON inputs, not exported summaries,
and enforces one unique matching capture_id across all three source records:

1. Stage 078 media manifest (clip file and declared capture identity).
2. Stage 079 paired timing metadata (clip ID, scripted inputs and timestamps).
3. Stage 077 paired contact trace (clip ID and contact-label observations).

It reuses bounded Stage 078 SHA-256 exact-byte checks, Stage 079 timing
checks, and Stage 077 contact/numeric/event checks.

## Private usage

When ten distinct source recordings are available, prepare files inside
the ignored local_reports directory:

- local_reports/media-manifest.json: Stage 078 input manifest.
- local_reports/timing-suite.json: object with a traces array containing all
  five **input** timing record pairs (not derived timing summaries).
- local_reports/contact-suite.json: object with a traces array containing
  all five **input** contact record pairs (not derived contact summaries).
- local_reports/captures/: the actual private clips named by the manifest.

Run the joiner from the checkout root:

    PYTHONPATH=src python -m heman_tools.capture_evidence_join \
      --media local_reports/media-manifest.json \
      --timing local_reports/timing-suite.json \
      --contacts local_reports/contact-suite.json \
      --out local_reports/joined-evidence-summary.json

    PYTHONPATH=src python -m unittest discover -s tests -v

The joiner requires exactly ten declared media sessions and five unique
paired timing and contact scenarios. To report incomplete evidence, use
the Stage 078 manifest checker (which reports missing recordings).

The resulting local JSON exposes only per-scenario boolean results,
bounded counts and blocker names: no capture IDs, paths, SHA digests,
raw coordinates, timestamps or original pixels.

## Source evidence remains unverified

The test suite uses invented strings stored in files ending in .mov; the
bytes are NOT valid actual video. Even if all numerical declarations agree
and a structural pass is produced, the tool permanently reports:

- genuine_ios_capture_provenance_authenticated = false
- recorded_video_frames_decoded = false
- original_ios_frame_rate_established = false
- cross_device_absolute_clock_synchronized = false
- original_gameplay_physics_verified = false
- automatic_collision_export_permitted = false

No original IPA, footage, screenshots, proprietary data or actual video
measurements are added to GitHub. The eight-category manual evidence gate
remains required, and Switch gameplay physics are untouched.
