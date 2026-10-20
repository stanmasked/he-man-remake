# Private iOS IPA inventory (source-only tool)

The Switch prototype remains asset-free. To study the original iOS release
from a legally held local copy, use this **offline metadata inspector**.

```sh
python3 tools/inspect_heman_ipa.py "/absolute/private/path/game.ipa" \
  --verify-crc --output "/absolute/private/path/inventory.json"
```

The script reads the IPA as a ZIP; it does not extract files, connect to a
network, or copy images, scripts, level binaries, sound, or any other original
assets into this repository. Output contains only aggregate counts, bundle
version, basic supported device metadata, and relative-path parity statistics
between the two built-in resolution variants. A matching size + CRC32 is an
inventory indicator, **not** proof that runtime assets are interchangeable.

Keep both the original IPA and JSON report **outside** the repository.
The existing `.gitignore` deliberately excludes `*.ipa` and
`local_reports/`; do not work around those guards.

CI exercises this utility exclusively with fabricated ZIP fixtures from
`tests/test_inspect_heman_ipa.py`. The private IPA is neither needed
nor uploaded to GitHub Actions.

The metadata report is an initial planning input, not a playable port,
a decompilation, confirmation of physics fidelity, or authorization to
redistribute any third-party assets. Conversion and rendering of owned
resources, if developed later, should run locally only.
