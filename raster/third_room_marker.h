#ifndef HEMAN_THIRD_ROOM_MARKER_H
#define HEMAN_THIRD_ROOM_MARKER_H
#include <stdint.h>

/* Optional stage 3 display, source-authored and never active in two-room NRO.
   For stages 0/1, delegates to the existing verified stage marker. */
int hm_three_room_marker(uint32_t *pixels, uint32_t width, uint32_t height,
                         uint32_t stride, uint8_t stage);
#endif
