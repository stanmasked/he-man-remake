# Stage 078 — private gameplay-capture file receipts

The Stage 077 scenario validators need authentic, independently recorded
material. A plausible JSON trace alone is not a recording. Stage 078 provides
a **read-only, bounded private file inventory** for ten intended recordings:
five contact scenarios × original iOS and Switch prototype.

This is a file *integrity* preflight only. It cannot tell whether a valid
video is encoded, whether iOS gameplay is shown, whether timings correspond,
or whether observed contact labels are true.

## Local manifest format

Create \`local_reports/capture-manifest.json\`:

\`\`\`json
{
  "protocol_version": 1,
  "captures": [
    {
      "scenario_id": "landing",
      "platform": "ios",
      "capture_id": "local-landing-ios-001",
      "media_relpath": "captures/local-landing-ios-001.mov",
      "declared_source": "ios_device"
    }
  ]
}
\`\`\`

The example is an illustrative **manifest entry**, not evidence that such a
file or working iOS device exists.

For iOS, permitted \`declared_source\` labels are \`ios_device\`,
\`ios_emulator\` or \`synthetic_fixture\`. For Switch, they are
\`switch_hardware\`, \`switch_emulator\` or \`synthetic_fixture\`.
All labels are **unverified user declarations**, not authentication.

The tool accepts an incomplete manifest (even \`"captures": []\`) and
reports explicit \`capture_not_supplied\` blockers for the missing
scenario/platform combinations. Missing declared files are also blockers.
A 10-file structural pass cannot authenticate source footage.

Put files only in the local, gitignored \`local_reports/captures/\`
directory, each with a simple \`.mov\`, \`.mp4\`, or \`.mkv\` name.
Paths, symlinks, excessive archive sizes and reused capture identifiers are
rejected. The tool hashes no more than 512 MiB per video and 1 GiB total,
reading in bounded chunks. Identical SHA-256 digests between different
declared captures are flagged as reused material.

## Run entirely locally

\`\`\`sh
PYTHONPATH=src python -m heman_tools.capture_media_receipts \
  --manifest local_reports/capture-manifest.json \
  --out local_reports/capture-receipts.json

PYTHONPATH=src python -m unittest discover -s tests -v
\`\`\`

The private JSON output includes clip byte counts and SHA-256 digests.
Neither the original videos nor these derived fingerprints should be
committed to public GitHub. GitHub Actions runs **19 entirely synthetic
tests**, with invented byte strings instead of copyrighted videos.
The tool does not parse video frames; even a fake file with a media extension
can pass its structural check, which is why all evidence-authentication flags
are permanently false.

## Actual original gameplay is still missing

The user's original iOS IPA is a legacy armv7 game, and its ability to launch
in a compatible environment has *not* been confirmed. The provisional
60 FPS contact protocols must not be mistaken for known original timing.
Before an actual game-physics assessment: establish a lawful working source
capture environment; inspect genuine input/video timestamps, mapping and
frame drop behavior; compare independently measured stationary landmarks;
then run Stages 076–077 on privately recorded, non-synthetic observations.

Hardcoded report limits:

\`source_video_decoding_performed = false\`,
\`video_frame_timestamps_verified = false\`,
\`controller_input_alignment_verified = false\`,
\`original_ios_recording_provenance_authenticated = false\`,
\`original_gameplay_physics_verified = false\`,
\`automatic_collision_export_permitted = false\`.

The eight-category evidence gate remains mandatory, and this stage does not
change native or Switch gameplay.
