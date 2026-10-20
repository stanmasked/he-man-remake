# Stage 081 — private legacy iOS launch-readiness preflight

He-Man's original iOS package is not a Switch executable. Before attempting
real contact observations (GitHub issue #81), inspect the app's bundle and
executable header **without extraction**. This is an offline metadata
preflight, not iOS emulation, decryption, code signing or a game launch.

## Private command

Keep the source IPA outside public GitHub and run from the checkout root:

    PYTHONPATH=src python -m heman_tools.ios_launch_preflight \
      --ipa /private/He-Man-v2.0.0.ipa \
      --out local_reports/ios-launch-preflight.json

    PYTHONPATH=src python -m unittest discover -s tests -v

The output must be in the gitignored local_reports directory. The analyzer
reads only Info.plist and the declared bundle executable inside a bounded
IPA archive. ZIP names are validated; original resources are not extracted.

## What is actually tested

- One-app-bundle structure and a simple declared executable name.
- Thin **32-bit** Mach-O file header, CPU type/subtype, executable type,
  load-command bounds and nonduplicated iOS version/encryption/signature
  commands; fat Mach-O and 64-bit formats explicitly unsupported.
- The app minimum iOS version (Info.plist) against LC_VERSION_MIN_IPHONEOS
  in Mach-O load commands, when present.
- SDK version as a number declared by the binary, not a runtime test.
- cryptid value, which is not decryption, licensing or installability
  assessment. cryptid = 0 **does not prove** successful execution.
- Declared device families, GPU feature strings and screen orientations.

For the user's own v2.0.0 IPA, the executable has an ARMv7 32-bit Mach-O
header. It declares an iOS 4.3 minimum, iPhoneOS 6.1 SDK and the
opengles-2 capability. These are static source observations only.

## Real capture prerequisites

1. Establish a lawful, compatible execution environment for the user's
   original application; do not presume modern iOS or macOS can execute it.
   Valid signing, supported graphics and installability must be assessed
   separately without publication of proprietary assets.
2. Observe that the application really starts and input/graphics work.
3. Privately identify actual touch input mapping and measured frame rate.
   Stage 077's 60 FPS input schedule remains **provisional**.
4. Privately record gameplay and input timestamps, then use Stages 077–080
   to check contact events, video integrity, relative timing and identity.
5. Meet the eight-category first-level manual evidence gate before making
   changes to the native Switch collision model.

The report permanently records real_ios_app_started=false,
ios_gameplay_frames_recorded=false, original_ios_frame_rate_measured=false,
code_signature_validity_verified=false,
original_gameplay_physics_verified=false and
automatic_collision_export_permitted=false.

Only fabricated Mach-O and IPA ZIP fixtures are used in CI (20 tests). No
original executable, IPA, footage, screenshots, extracted textures or
private original-game measurements enter public GitHub. Switch gameplay
remains unchanged.
