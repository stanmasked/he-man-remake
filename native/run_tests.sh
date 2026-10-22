#!/bin/sh
# Compile only independently authored C99 source and synthetic host tests.
set -eu

CC=${1:-cc}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT HUP INT TERM

"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/tests/test_core.c" \
  -lm -o "$TMP/test_core"

# Stage172: independently authored C99 sprite clock oracle. Synthetic
# frame boundaries only; no proprietary resources or original traces.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_sprite_clock.c" \
  "$ROOT/native/tests/test_sprite_clock.c" \
  -lm -o "$TMP/test_sprite_clock"

# Stage174: source-free reproduction of the original bounded app tick
# accumulator (synthetic elapsed milliseconds only).
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_app_tick_scheduler.c" \
  "$ROOT/native/tests/test_app_tick_scheduler.c" \
  -o "$TMP/test_app_tick_scheduler"

# Stage175: exercise the actual scheduler + sprite clock together, including
# a full synthetic second, the wall-time cap, and pause/resume behavior.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_app_tick_scheduler.c" \
  "$ROOT/native/src/heman_sprite_clock.c" \
  "$ROOT/native/tests/test_tick_animation_integration.c" \
  -lm -o "$TMP/test_tick_animation_integration"
"$TMP/test_tick_animation_integration"
"$TMP/test_app_tick_scheduler"
"$TMP/test_sprite_clock"

# Stage 102: source-referenced, privately importable level 1-1 lore mechanics.
# No original iOS map/geometry or commercial assets. Tested as pure C99.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_level11_lore.c" \
  "$ROOT/native/tests/test_level11_lore.c" \
  -o "$TMP/test_level11_lore"

# Stage 104: replay the *actual* C99 physics step before granting Level 1-1
# gate/pickup progression. All world geometry in the test is fictional.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_level11_lore.c" \
  "$ROOT/native/src/heman_level11_native_contacts.c" \
  "$ROOT/native/tests/test_level11_native_contacts.c" \
  -lm -o "$TMP/test_level11_native_contacts"

# Stage 105: a native-owned button latch derives rising attack edges and
# executes hm_step without accepting forged after-frame states from callers.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_level11_lore.c" \
  "$ROOT/native/src/heman_level11_native_contacts.c" \
  "$ROOT/native/src/heman_level11_native_session.c" \
  "$ROOT/native/tests/test_level11_native_session.c" \
  -lm -o "$TMP/test_level11_native_session"

# Stage108: versioned, asset-free native Level1-1 session serialization
# and genuine post-save progression with sticky gated collectible repair.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_level11_lore.c" \
  "$ROOT/native/src/heman_level11_native_contacts.c" \
  "$ROOT/native/src/heman_level11_native_session.c" \
  "$ROOT/native/src/heman_level11_snapshot.c" \
  "$ROOT/native/tests/test_level11_snapshot.c" \
  -lm -o "$TMP/test_level11_snapshot"

# Stage111: this exact fictional C99 world/input/save integration is also
# compiled into switch_lore/heman_level11_lore_lab.nro (separate target).
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_level11_lore.c" \
  "$ROOT/native/src/heman_level11_native_contacts.c" \
  "$ROOT/native/src/heman_level11_native_session.c" \
  "$ROOT/native/src/heman_level11_snapshot.c" \
  "$ROOT/native/src/heman_level11_lab.c" \
  "$ROOT/native/tests/test_level11_lab.c" \
  -lm -o "$TMP/test_level11_lab"
"$TMP/test_level11_lab"

# Stage113: two independently recoverable journal slots and actual
# separate-process cold-start file IO (source-only C99, synthetic world).
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_level11_lore.c" \
  "$ROOT/native/src/heman_level11_native_contacts.c" \
  "$ROOT/native/src/heman_level11_native_session.c" \
  "$ROOT/native/src/heman_level11_snapshot.c" \
  "$ROOT/native/src/heman_level11_lab.c" \
  "$ROOT/native/src/heman_level11_journal.c" \
  "$ROOT/native/tests/test_level11_journal.c" \
  -lm -o "$TMP/test_level11_journal"
"$TMP/test_level11_journal"
"$TMP/test_level11_journal" cold-write "$TMP/heman-progress"
"$TMP/test_level11_journal" cold-read "$TMP/heman-progress"
"$TMP/test_level11_journal" cold-upgrade "$TMP/heman-progress"
"$TMP/test_level11_journal" cold-read-upgrade "$TMP/heman-progress"
# Corrupt newest slot and prove a brand-new process recovers old slot.
printf '\001' >> "$TMP/heman-progress.1"
"$TMP/test_level11_journal" cold-read "$TMP/heman-progress"
# Rebuild generation 2, then flip a protected payload byte without updating
# the digest. A separate reader must reject it and recover generation 1.
"$TMP/test_level11_journal" cold-upgrade "$TMP/heman-progress"
"$TMP/test_level11_journal" cold-corrupt "$TMP/heman-progress"
"$TMP/test_level11_journal" cold-read "$TMP/heman-progress"
# Rebuild generation 2 again, then test a physically short on-disk record.
"$TMP/test_level11_journal" cold-upgrade "$TMP/heman-progress"
truncate -s 60 "$TMP/heman-progress.1"
"$TMP/test_level11_journal" cold-read "$TMP/heman-progress"
# Simulate an interrupted write to the inactive disk slot; preserve slot 0.
"$TMP/test_level11_journal" cold-torn-write "$TMP/heman-progress"
"$TMP/test_level11_journal" cold-read "$TMP/heman-progress"

# Stage113 adapter-level host shim: compile the actual SD adapter against a
# minimal mock libnx surface and a temporary sdmc: directory. This tests file
# handling, slot recovery and error propagation, not real Switch SD services.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/tests/mock_libnx" -I"$ROOT/native/include" \
  -I"$ROOT/switch_lore/source" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_level11_lore.c" \
  "$ROOT/native/src/heman_level11_native_contacts.c" \
  "$ROOT/native/src/heman_level11_native_session.c" \
  "$ROOT/native/src/heman_level11_snapshot.c" \
  "$ROOT/native/src/heman_level11_lab.c" \
  "$ROOT/native/src/heman_level11_journal.c" \
  "$ROOT/switch_lore/source/sd_journal.c" \
  "$ROOT/native/tests/test_switch_lore_sd_adapter.c" \
  -lm -o "$TMP/test_switch_lore_sd_adapter"
mkdir -p "$TMP/sd-adapter-root/sdmc:"
(cd "$TMP/sd-adapter-root" && "$TMP/test_switch_lore_sd_adapter")
mkdir -p "$TMP/sd-adapter-premounted-root/sdmc:"
(cd "$TMP/sd-adapter-premounted-root" && "$TMP/test_switch_lore_sd_adapter" pre-mounted)

"$TMP/test_level11_snapshot"
"$TMP/test_level11_native_session"
"$TMP/test_level11_native_contacts"
"$TMP/test_level11_lore"

"$TMP/test_core"


# Mask geometry tests are separate from the rectangular gameplay core.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/tests/test_mask.c" \
  -lm -o "$TMP/test_mask"
"$TMP/test_mask"


"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_mask_motion.c" \
  "$ROOT/native/tests/test_mask_motion.c" \
  -lm -o "$TMP/test_mask_motion"
"$TMP/test_mask_motion"

# Main C99 game loop with the optional borrowed pixel mask grid.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/tests/test_mask_game.c" \
  -lm -o "$TMP/test_mask_game"
"$TMP/test_mask_game"


# Full-grid validation must occur once at frame entry, while external overlap
# calls remain safe and malformed grids must leave actor state unchanged.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/tests/test_mask_validation_once.c" \
  -lm -o "$TMP/test_mask_validation_once"
"$TMP/test_mask_validation_once"

# Verify the same asset-free ASCII world adapter used by the Switch binary.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/switch/source" \
  "$ROOT/switch/source/probe_view.c" \
  "$ROOT/switch/tests/test_probe_view.c" \
  -lm -o "$TMP/test_probe_view"
"$TMP/test_probe_view"

# Execute a pure-C99 scripted boot diagnostic using the exact Switch engine
# and viewport sources (the iOS IPA must never be present in CI).
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/switch/source" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/switch/source/probe_view.c" \
  "$ROOT/switch/source/probe_selfcheck.c" \
  "$ROOT/switch/tests/test_probe_selfcheck.c" \
  -lm -o "$TMP/test_probe_selfcheck"
"$TMP/test_probe_selfcheck"

# Synthetic one-enemy combat subsystem, independent of original game assets.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/tests/test_combat.c" \
  -lm -o "$TMP/test_combat"
"$TMP/test_combat"

# Verify atomic combined physics/combat state transitions, including
# rollback and reproducibility, without source assets or libnx.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/tests/test_session.c" \
  -lm -o "$TMP/test_session"
"$TMP/test_session"

# The exact combined-physics-and-combat startup diagnostic that ships in NRO.
# Keep executable on the host without Nintendo SDK or original game assets.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/switch/source" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/switch/source/session_selftest.c" \
  "$ROOT/switch/tests/test_session_selftest.c" \
  -lm -o "$TMP/test_session_selftest"
"$TMP/test_session_selftest"

# One-time synthetic pickup heal, HP saturation and atomic rollback.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/tests/test_session_pickup.c" \
  -lm -o "$TMP/test_session_pickup"
"$TMP/test_session_pickup"

# Standalone 180-frame deterministic input replay shared with the NRO.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/switch/source" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/switch/source/runtime_replay.c" \
  "$ROOT/switch/tests/test_runtime_replay.c" \
  -lm -o "$TMP/test_runtime_replay"
"$TMP/test_runtime_replay"

# Portable RGB test renderer is compiled into the same graphics NRO.
# Check deterministic pixels, clipping and untouched row-padding canaries.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/raster/raster_scene.c" \
  "$ROOT/raster/tests/test_raster_scene.c" \
  -lm -o "$TMP/test_raster_scene"
"$TMP/test_raster_scene"


# Stage 039: source-only near-range sword combat and actual enemy HP pixels.
# Uses identical session / renderer C sources as the devkitPro attack NRO.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/raster/raster_scene.c" \
  "$ROOT/raster/tests/test_attack_raster.c" \
  -lm -o "$TMP/test_attack_raster"
"$TMP/test_attack_raster"


# Stage 040: real contact damage, cooldown immunity and native defeat
# recovery. Inspect original C99 renderer HP bars and respawn marker too.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/raster/raster_scene.c" \
  "$ROOT/raster/tests/test_damage_respawn_raster.c" \
  -lm -o "$TMP/test_damage_respawn_raster"
"$TMP/test_damage_respawn_raster"

# Stage 040: exact C99 damage, invulnerability, death and next-frame recovery;
# verify the three real player HP HUD ticks and no unexpected movement.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/raster/raster_scene.c" \
  "$ROOT/raster/tests/test_contact_recovery_raster.c" \
  -lm -o "$TMP/test_contact_recovery_raster"
"$TMP/test_contact_recovery_raster"


# Stage 043: prove the same C99 hero can move, face left and defeat the
# contact enemy after genuine next-frame respawn; assert live HUD pixels.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/raster/raster_scene.c" \
  "$ROOT/raster/tests/test_post_respawn_controls_raster.c" \
  -lm -o "$TMP/test_post_respawn_controls_raster"
"$TMP/test_post_respawn_controls_raster"

# Stage 046: rehearse real NeXium post-respawn X test against the unchanged
# C99 game state and RGBA8888 renderer, on GCC and Clang.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/raster/raster_scene.c" \
  "$ROOT/raster/tests/test_post_respawn_sword_raster.c" \
  -lm -o "$TMP/test_post_respawn_sword_raster"
"$TMP/test_post_respawn_sword_raster"


# Stage 048: activate a synthetic checkpoint away from spawn, suffer real
# contact defeat, recover at that checkpoint, defeat the contact enemy, then
# trigger a hazard and verify the next native respawn uses the checkpoint.
# Examine checkpoint flag, world-X marker, HP and respawn HUD pixels.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/raster/raster_scene.c" \
  "$ROOT/raster/tests/test_checkpoint_respawn_combat_raster.c" \
  -lm -o "$TMP/test_checkpoint_respawn_combat_raster"
"$TMP/test_checkpoint_respawn_combat_raster"


# Stage 052: same-core synthetic checkpoint contact death, next-frame
# recovery, then two real C99 sword strikes against live rendered HP HUD.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/raster/raster_scene.c" \
  "$ROOT/raster/tests/test_checkpoint_postdefeat_sword_raster.c" \
  -lm -o "$TMP/test_checkpoint_postdefeat_sword_raster"
"$TMP/test_checkpoint_postdefeat_sword_raster"

# Stage 066: portable Minus-button pause adapter. Pause/resume must freeze
# real native physics, combat timers and events without breaking rollback.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/src/heman_pause.c" \
  "$ROOT/native/tests/test_pause.c" \
  -lm -o "$TMP/test_pause"
"$TMP/test_pause"

# The PAUSED overlay is independent of existing raster_scene rendering.
# Check deterministic pixels and row padding using standalone C99.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/raster" \
  "$ROOT/raster/pause_overlay.c" \
  "$ROOT/raster/tests/test_pause_overlay.c" \
  -lm -o "$TMP/test_pause_overlay"
"$TMP/test_pause_overlay"

# Stage 067: actual C99 HM_EXIT then explicit A transition to a second
# independently written room, with atomic rollback and final-level guard.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/src/heman_stage_chain.c" \
  "$ROOT/native/src/heman_synthetic_room2.c" \
  "$ROOT/native/tests/test_stage_chain.c" \
  -lm -o "$TMP/test_stage_chain"
"$TMP/test_stage_chain"

# Minimal source-only stage number indicator with stride canaries.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/raster" \
  "$ROOT/raster/stage_marker.c" \
  "$ROOT/raster/tests/test_stage_marker.c" \
  -lm -o "$TMP/test_stage_marker"
"$TMP/test_stage_marker"

# Stage 068: assert the EXACT shared source-authored stage-2 geometry used
# by the Switch NRO, and exercise its pickup/checkpoint/hazard/exit events
# through the actual native world simulation (no replica fixture).
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/src/heman_synthetic_room2.c" \
  "$ROOT/native/tests/test_synthetic_room2.c" \
  -lm -o "$TMP/test_synthetic_room2"
"$TMP/test_synthetic_room2"

# Stage 069: optional room-2 ZR dash uses real C99 physics and a genuine
# frame-based recharge; toggling Minus cannot spend dash/recovery frames.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/src/heman_pause.c" \
  "$ROOT/native/src/heman_dash.c" \
  "$ROOT/native/src/heman_synthetic_room2.c" \
  "$ROOT/native/tests/test_dash.c" \
  -lm -o "$TMP/test_dash"
"$TMP/test_dash"

# Pixel-accurate ZR HUD proof for ready, active, recovery and padding.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/raster" -I"$ROOT/native/include" \
  "$ROOT/raster/dash_hud.c" \
  "$ROOT/raster/tests/test_dash_hud.c" \
  -lm -o "$TMP/test_dash_hud"
"$TMP/test_dash_hud"


# Stage 083: final synthetic second-room exit freezes native C99 session,
# while B resets the room and pause/invalid inputs cannot leak a game tick.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/src/heman_pause.c" \
  "$ROOT/native/src/heman_dash.c" \
  "$ROOT/native/src/heman_finale.c" \
  "$ROOT/native/tests/test_finale.c" \
  -lm -o "$TMP/test_finale"
"$TMP/test_finale"

# Draw actual FINISH status from native terminal state, without affecting
# framebuffer row padding or claiming source-game victory semantics.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/raster" \
  "$ROOT/raster/finale_overlay.c" \
  "$ROOT/raster/tests/test_finale_overlay.c" \
  -lm -o "$TMP/test_finale_overlay"
"$TMP/test_finale_overlay"


# Stage 086: opt-in ZL landing strike, genuinely simulated by the same
# portable physics/combat/finale state machines as the Switch prototype.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/src/heman_pause.c" \
  "$ROOT/native/src/heman_dash.c" \
  "$ROOT/native/src/heman_finale.c" \
  "$ROOT/native/src/heman_air_smash.c" \
  "$ROOT/native/tests/test_air_smash.c" \
  -lm -o "$TMP/test_air_smash"
"$TMP/test_air_smash"


# Stage 086 opt-in Aerial Smash HUD status/pixel and stride integrity.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" -I"$ROOT/raster" \
  "$ROOT/raster/air_smash_hud.c" \
  "$ROOT/raster/tests/test_air_smash_hud.c" \
  -lm -o "$TMP/test_air_smash_hud"
"$TMP/test_air_smash_hud"


# Stage 088: isolated third training room. The current real Switch course
# remains two rooms until a separate opt-in stage-chain integration.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/src/heman_synthetic_room3.c" \
  "$ROOT/native/tests/test_synthetic_room3.c" \
  -lm -o "$TMP/test_synthetic_room3"
"$TMP/test_synthetic_room3"


# Stage 089: native transactional 0→1→2 session chain with true engine
# CLEAR/A events, including a real third room and no duplicate stage.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" \
  "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/src/heman_combat.c" \
  "$ROOT/native/src/heman_session.c" \
  "$ROOT/native/src/heman_three_room_chain.c" \
  "$ROOT/native/src/heman_synthetic_room3.c" \
  "$ROOT/native/tests/test_three_room_chain.c" \
  -lm -o "$TMP/test_three_room_chain"
"$TMP/test_three_room_chain"

# Source-authored stage-3 badge, with legacy stage-1/2 pixels untouched.
"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/raster" \
  "$ROOT/raster/stage_marker.c" \
  "$ROOT/raster/third_room_marker.c" \
  "$ROOT/raster/tests/test_third_room_marker.c" \
  -lm -o "$TMP/test_third_room_marker"
"$TMP/test_third_room_marker"
