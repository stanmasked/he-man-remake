#ifndef HEMAN_PAUSE_OVERLAY_H
#define HEMAN_PAUSE_OVERLAY_H

#include <stdint.h>
/* Add asset-free PAUSED lettering to an already rendered 640x360 RGBA view.
   Reject invalid sizes/pointers before writing any pixel. Stride in pixels. */
int hm_pause_overlay(uint32_t *pixels, uint32_t width,
                     uint32_t height, uint32_t stride);
#endif
