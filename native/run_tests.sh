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
