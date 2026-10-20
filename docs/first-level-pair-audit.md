# Stage 072: source-private first-level parity check

Compare the stored bytes for one selected level and candidate map across
the two screen variants of a local iOS IPA:

```bash
PYTHONPATH=src python -m heman_tools.first_level_pair_audit \
  --ipa /path/to/original.ipa \
  --level MULevel1-1.lvl --map MUMap1-1.map \
  --out local_reports/level1-pair.json
```

The report contains only byte lengths, numeric header fields and equality
booleans. Resource contents are not extracted or included in reports. Output
is restricted to the ignored local_reports directory.

**Limit:** Even matching level and map bytes do not verify that these
resources are linked at runtime or that collision cells are solid.
The eight checks in docs/first-level-evidence-gate.md remain necessary.
This tool does not modify the Switch prototype.

Synthetic regression tests use fabricated ZIP data only.
