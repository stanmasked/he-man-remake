# Stage134 — rollback to a genuinely earlier game-written state when the latest save is torn

Stage119 proved native fallback from an older intact record when a
host-synthesized newer record was truncated. But both snapshots contained
the same progress. Stage133 introduced a **real second save** made by
the unmodified homebrew guest after genuine D-pad movement, producing
different protagonist x positions in two independent 120-byte records.

Stage134 combines these results in a distinct, fail-closed experiment:

1. Obtain the actual independent guest first-save receipt and the
   Stage133 **real second SD-save receipt**. The source virtual SD must
   contain *two valid 120-byte, distinct game-origin records*,
   identical earned collectibles/world seal but different player x and
   strictly consecutive generations.
2. Use the source-root descriptor-anchored `O_NOFOLLOW` reader to copy
   only the two original 120-byte records into an isolated CI-only root.
   Preserve older slot0 unchanged; truncate newest slot1 to 64 bytes.
   Independently audit exactly one surviving older valid slot0.
   **Never modify or publish the original two records.**
3. Launch an **eighth genuine pinned NeXium host process** using the same
   unchanged Switch NRO, with fresh empty RAM, and inject exactly the
   four ZL+R cold-restore kernel NPAD edges.
4. Read authentic guest frame_rx PNGs and require frame540 to match the
   **first, older gameplay-written** saved scene, not the moved player's
   second saved scene. The old and new save positions must visibly
   differ by at least eight native units.
5. Independently re-audit all four files: both source game-origin saves
   and both isolated fixture slots must keep the same SHA-256 hashes
   after the restore. The damaged newer record may not be accepted.

No iOS assets or save files, private paths or raw journal bytes are
committed; only metadata, logs, checksums and guest-rendered PNGs are
published. Separate mock-only tests fail closed on lost source
attestation, wrong rollback, changed journal bytes, extra movement
and reused host process directories.

**Caveat:** The second source SD save in this experiment really comes
from in-game movement, but the truncation is still deliberately
introduced by a *host-side fixture editor in an isolated copy*.
It is not an actual sudden loss of power, a physical Nintendo Switch
test, or an authentic iOS Level1-1 scene.
