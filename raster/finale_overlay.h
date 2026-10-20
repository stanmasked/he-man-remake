#ifndef HEMAN_FINALE_OVERLAY_H
#define HEMAN_FINALE_OVERLAY_H
#include <stdint.h>

/* Draw source-authored FINISH panel only after a terminal second-room exit.
   PAUSED has visual priority. No proprietary fonts or artwork.
   Reject malformed dimensions and flags without modifying the target. */
int hm_finale_overlay(uint32_t *pixels, uint32_t width, uint32_t height,
                      uint32_t stride, uint8_t stage, uint8_t completed,
                      uint8_t paused);
#endif
