#ifndef HEMAN_PROBE_VIEW_H
#define HEMAN_PROBE_VIEW_H

#include <stddef.h>
#include "heman_core.h"

/* Source-only, libnx-independent 40x20 diagnostics. Each glyph is one tile.
   This is not a sprite renderer or a representation of original iOS art. */
#define HM_PROBE_COLS 40u
#define HM_PROBE_ROWS 20u
#define HM_PROBE_STRIDE (HM_PROBE_COLS + 1u)
#define HM_PROBE_BYTES (HM_PROBE_ROWS * HM_PROBE_STRIDE)

/* Writes HM_PROBE_ROWS NUL-terminated rows to out on success.
   Returns zero without modifying out on bad arguments/state. */
int hm_probe_render(const hm_world *world, const hm_state *state,
                    char *out, size_t out_len);

/* Place a visible synthetic enemy glyph without overwriting the player (@).
   Invalid arguments leave the original buffer intact; offscreen is OK. */
int hm_probe_overlay_marker(const hm_world *world, const hm_state *state,
                            char *out, size_t out_len,
                            float x, float y, char glyph);

#endif
