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
