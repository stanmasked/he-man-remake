#ifndef HEMAN_STAGE_MARKER_H
#define HEMAN_STAGE_MARKER_H
#include <stdint.h>
/* Asset-free HUD marker: 1 or 2 for the synthetic two-stage exercise.
   Reject malformed dimensions/stage before touching the frame buffer. */
int hm_stage_marker(uint32_t *pixels,uint32_t width,uint32_t height,
                    uint32_t stride,uint8_t stage);
#endif
