# Stage 101 — independently revalidate real pinned NeXium frame_rx receipts

**Original authentic run:** [GitHub Actions #39515325336](https://github.com/stanmasked/he-man-remake/actions/runs/39515325336)
on experimental PR #107 commit `b7109dcaa009391b8a193e9ccae3f647c9105540`.

The pinned NeXium debug_boot launched the unmodified opt-in 3-room
`heman_three_room_probe.nro` for 6193 received guest frames, completing
its native guest CPU test and production runner. The independent kernel
`[hid-publish]` check **succeeded**: all 16 expected Right/A/B press
and release state changes were observed in exclusive guest NPAD shared
memory, with 17 kernel publication records. The GitHub Actions job's
*next* step failed **before the Python optical validator ran**, because
a greedy `sed` command erased the SHA-256 hash rather than normalizing
just the absolute NRO filename. The original NRO SHA receipts actually
match:

`cfdd2fe65a5406d33de3eb499076c3389b8f32c83c2f4975e42e14426200d977`

This bug is fixed in PR #107's workflow. The original run's immutable
artifact [#12308038833](https://github.com/stanmasked/he-man-remake/actions/runs/39515325336/artifacts/12308038833)
contains all **18 genuine source-generated guest PNG images**, real
`raster-runner.log`, `raster-stdout.log`, and kernel/input evidence.

A local independent offline audit of the original artifact confirmed
real visible stage sequence 1→2→3, CLEAR at 75/465/505/1045/1080/1120,
FINISH at 1045/1080/1120, source native third-room x628→x458
hazard/respawn, x698 jump, x828 terminal exit, a byte-for-byte frozen
FINISH image and real B replay at x48. These images came from the
unchanged pinned NeXium guest frame_rx, **not the host C99 raster**.

To make the optical result a separate auditable GitHub CI receipt,
`revalidate-real-three-room-guest.yml` uses the GitHub Actions API to
download the **same immutable artifact from run #39515325336** with
read-only permissions; it checks the original NRO digests, original
runner completion and exact image count, then runs the unmodified
production `verify_nexium_hid_publication.py` and
`verify_nexium_three_room_pngs.py` readers against the original
artifacts. It uploads SHA-256 image manifests and the resulting
independent receipts.

This workflow does not make replacement screenshots, manipulate
guest RAM, alter frame order, edit the source .ipa, modify emulator
code or claim fidelity to original iOS content. It is separate from
building/running a new NRO. Genuine production proof remains
conditional on a fully successful archived artifact revalidation run.
