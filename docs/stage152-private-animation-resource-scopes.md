# Stage152 — first-level animation source scopes and resolution-pack divergence

## Actual owner-private iOS v2.0.0 resource observations

The original iOS IPA was inspected privately and read-only. The study
follows Stage151's **six** first-level objects with exact class-name
matches to **two** original physics-resource basenames. All six have the
serialized state label `idle`. That string is common across source
game content; it is **not** a proven animation sequence identity.

The original medium/extra-large screen-resource packs have:

| Original resource family | Compared resource pairs | Result |
|---|---:|---|
| Sprite sequence, sprite cut and single-frame metadata `.repo` | **3** | Exact bytes equal |
| Skeletal animation `.skel2d` files | **26** | Exact bytes equal |
| `sprite/SpriteSeqData.wad` | **1** | Same byte length but **29,638 bytes differ** |
| `sprite/SpriteResData.wad` | **1** | Same byte length but **7,882 bytes differ** |

The byte-difference count compares matching offsets in the two files.
**Difference does not establish a behavioral/animation change**: these
WADs may embed resolution-specific frame or sprite data even when
logical animations are shared. The `.repo` and skeleton pairs are
byte-identical, so silently substituting the WAD from another
screen pack would risk a mismatched asset pairing.

### First-level names are not immediately present in animation assets

For the two exact source physics-class basenames (associated with six
Level1-1 objects), a conservative raw UTF-16LE full-string and
length-prefixed UTF-16LE string scan found **no exact occurrences** in:

- The three sprite metadata repositories.
- The two sprite WADs.
- The 26 standalone skeletal-animation resources.

In contrast, the first-level linked objects' `idle` state label is
common in sprite-sequence content. The presence of `idle` anywhere
in an archive is not evidence that a specific actor class loads
or plays any particular animation.

The matched Level1 objects are a **specific small subset** of 159
source objects. No statement is made about the animation bindings
of the other 153, especially the player, enemies or effects.
Likewise, a missing *literal* class name does **not** rule out
indirect links through generic sprite definitions, script commands,
class tables, animation indexes or nontext resource handles.

## Implemented privacy-preserving checks

Module: `src/heman_tools/level1_animation_scope.py`.

It reuses the strict Stage150 level-object and physics-resource
decoders to identify exact class-name matches, then checks
three repository / two WAD / skeleton groups in both resolution
packs. It enforces:

- Exact byte parity of first-level and physics metadata pairs.
- Exact byte parity of the three sprite repositories and all
  skeleton pairs, but **NOT** of sprite WADs.
- A bounded and safe read for each ZIP file, with duplicate member
  rejection, symlink rejection, per-asset size caps, skeleton
  membership equality and total skeleton-byte budget.
- An explicitly **lexical** comparison of full UTF-16 and
  u16-length-prefixed UTF-16 class and state identifiers.
- Aggregate counters and fixed `false` game-behavior verification
  gates; no exported class names, actual states, sprites, frames,
  per-object location or source hash.

Owner-private command:

```sh
PYTHONPATH=src python -m heman_tools.level1_animation_scope \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/level1_animation_scope.json
```

The `local_reports/` folder is already gitignored. The original IPA
and any extracted copyrighted sprites must not be placed in public
GitHub/Actions, PR attachments or releases.

The public regression suite adds **25 wholly synthetic cases**
covering resolution-specific differing/identical WADs, positive and
negative class/state name matches, generic `idle` false positives,
independent skeleton membership (including both `.skel2d` and `.skeleton2d` suffixes), source-name nonfuzzy matching,
registry/skeleton parity failures, archive traversal/symlinks,
malformed physics metadata, size guards and output privacy.

## Next useful original-game research

Decode the **structure** of the sprite sequence/cut metadata and
sprite WAD lookup mechanism *privately* to establish a verifiable
resource-ID path. The static metadata byte equality is useful but
not a parser for sprite playback. After resolving that indirection,
test how a first-level object state selects a sequence and whether
the active shape or sprite frame changes over time.

**No actual animation switching, original hitbox changes, player
animation fidelity or physical Switch hardware proof is established
in Stage152.** The independently authored NRO remains a synthetic
technical test scene. No original animation bytes were imported.
