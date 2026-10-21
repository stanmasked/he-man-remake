# Stage114 — independent emulator SD-file receipt

The previous real guest [Stage113 NeXium run](https://github.com/stanmasked/he-man-remake/actions/runs/39639714060)
completed successfully and showed green SD-save and SD-load HUD indicators
together with the restored synthetic scene. Its evidence archive did not
include the two underlying journal files or an independent record of their
existence. That leaves open whether the emulator's filesystem actually
persisted 120-byte records or only acknowledged guest IPC.

This stage introduces an additional, **read-only** check immediately after
the real guest PNG oracle. It examines the run-isolated
\`NEXIUM_DATA_ROOT/sdmc/switch/heman_lore_lab/progress{0,1}.bin\` paths
using the existing format auditor, checks 120-byte lengths, nested
FNV-1a checksums, schema and world-binding consistency, and writes only
metadata and SHA-256 hashes to \`guest-sd-disk-receipt.json\`.

If the guest reports green SD success but no structurally valid record is
present in the isolated emulator SD directory, CI fails with
\`green_guest_hud_without_structurally_valid_sd_file\`. A guest-reported
failure with no record may still pass as a correctly distinguished safe
failure — it is explicitly **not** proof of a successful SD round trip.

The auditor does not modify, attach or upload raw save bytes. It does not
test commit durability, separate application process cold restart, physical
power loss or actual Nintendo Switch SD. The isolated SD directory is created
inside the CI workspace, never a personal user's SD data directory.

This is a stacked test-only PR. Do not modify the previously passing NRO or
the original iOS game assets.
