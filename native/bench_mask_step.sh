#!/bin/sh
# Asset-free CPU timing. Report only; never enforce timing thresholds in CI.
set -eu
CC=${1:-cc}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT HUP INT TERM

"$CC" -std=c99 -O2 -Wall -Wextra -Werror -pedantic \
  -I"$ROOT/native/include" \
  "$ROOT/native/src/heman_core.c" "$ROOT/native/src/heman_mask.c" \
  "$ROOT/native/tests/bench_mask_step.c" \
  -lm -o "$TMP/bench"
"$TMP/bench"
