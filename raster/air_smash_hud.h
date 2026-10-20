#ifndef HEMAN_AIR_SMASH_HUD_H
#define HEMAN_AIR_SMASH_HUD_H

#include <stdint.h>
#include "heman_air_smash.h"

/* Independent source-authored indicator for optional ZL training only.
   Pixel writes are bounded; invalid metadata causes zero writes. */
int hm_air_smash_hud(uint32_t *pixels, uint32_t width, uint32_t height,
                     uint32_t stride, const hm_air_smash_state *ability);
#endif
