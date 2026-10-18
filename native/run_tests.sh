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
