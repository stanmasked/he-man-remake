#ifndef HEMAN_DASH_HUD_H
#define HEMAN_DASH_HUD_H
#include <stdint.h>
#include "heman_dash.h"

/* Tiny ZR ability meter in unused first-row HUD space, optional room 2.
   Reject malformed targets or state before modifying any pixel. */
int hm_dash_hud(uint32_t *pixels, uint32_t width, uint32_t height,
                uint32_t stride, const hm_dash_state *dash);
#endif
