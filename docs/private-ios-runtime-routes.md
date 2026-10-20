# Stage 082 — private runtime dependencies and capture environment decision

Stage 081 verified the privately held game's ARMv7 executable metadata.
Stage 082 counts its dynamically linked system frameworks and libraries
through bounded, read-only 32-bit Mach-O load-command parsing. Import names
are *not* emitted to the public repository or source-derived JSON reports.

## Private scan

Keep the user's original IPA off GitHub. Run from the project root:

    PYTHONPATH=src python -m heman_tools.ios_runtime_dependencies \
      --ipa /private/He-Man-v2.0.0.ipa \
      --out local_reports/private-runtime-dependencies.json

The JSON stays in the ignored local_reports directory and contains only
dependency counts grouped by load kind/path category, a few generic graphics
and UIKit flags, and explicit false runtime-validation gates. No original
executable, texture, gameplay frame or dependency path is exported.

The original iOS v2.0.0 binary has **33** linked dylib/framework imports.
This count is a **static dependency inventory**, not proof that imports resolve
under a given emulator, or that every framework is exercised at runtime.

## Where to attempt actual capture

### Preferred experimental route: legacy physical Apple device

Apple states that **iOS 10 is the last iOS version capable of launching
32-bit apps**. Devices such as the iPhone 5/5c and fourth-generation iPad
have 32-bit processors and supported OpenGL ES 2.0 historically.
A genuine, compatible device *already running iOS 10 or earlier* is therefore
a more plausible starting point than current iOS or macOS. The original IPA's
actual installability, ownership-based entitlement, signing, launch, audio,
touch input, graphics and gameplay remain **unknown**.

Apple QuickTime Player supports capturing a connected iPhone/iPad screen
through File → New Movie Recording; select the connected device as camera,
then save the recording **privately**. For legacy wired screen capture,
verify that the device and its USB/Lightning connection appear in QuickTime
before attempting experiments. Capture support for any particular vintage
device is NOT proven by these instructions.

Primary references (checked October 20, 2026):
- https://developer.apple.com/news/upcoming-requirements/?id=06062022a
- https://developer.apple.com/library/archive/documentation/OpenGLES/Conceptual/OpenGLESHardwarePlatformGuide_iOS/OpenGLESPlatforms/OpenGLESPlatforms.html
- https://support.apple.com/en-mide/guide/quicktime-player/qtp356b55534/mac

### Secondary, experimental: touchHLE

touchHLE's **October 1, 2026** documentation states it currently supports
some iPhone OS 2.x/3.x and iOS 4.0.x games. The present IPA declares a
minimum iOS **4.3**; hence its supported range does not yet cover that
declared minimum. The emulator authors also warn that most early games are
not compatible. Do not present touchHLE as a working original-game runtime.
Verify current upstream support again before any later experiment.

References:
- https://touchhle.org/faq.html
- https://github.com/touchHLE/touchHLE/blob/trunk/CHANGELOG.md

### Not suitable as direct runtime

Modern iOS 11+ does not launch 32-bit iOS apps, per Apple's developer
documentation. Modern macOS cannot natively execute an old iOS ARMv7 app
merely because it is a Mac, and desktop 32-bit app compatibility is a
different question from historical iPhone OS framework availability.

## Evidence gate for future source video

Record facts in order, without inventing success:

1. Identify lawful compatible device/runtime and inspect iOS version,
   genuine physical hardware capabilities and signed app installability.
2. Confirm an actual original-game **launch** and a visible game frame.
3. Observe touchscreen control equivalence and **measure** native timing;
   the Stage 077 nominal 60 FPS is still a hypothesis.
4. Capture the five contact scenarios privately and securely. Keep genuine
   video, decoded frames, SHA-256 receipts and input logs outside GitHub.
5. Use Stages 077–080 to validate contact event coverage, timing, media
   identity and coordinate calibration before considering physics transfer.

This tool never runs the app, assesses entitlement, validates signing,
decodes gameplay or exports collision masks. The Switch prototype and its
existing ZR dash are not changed. Original physics fidelity remains false.

All CI tests use fictional Mach-O byte arrays and fabricated ZIPs.
