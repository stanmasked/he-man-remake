#ifndef HEMAN_THIRD_ROOM_MARKER_H
#define HEMAN_THIRD_ROOM_MARKER_H
#include <stdint.h>

/* Optional stage 3 display, source-authored and never active in two-room NRO.
   For stages 0/1, delegates to the existing verified stage marker. */
int hm_three_room_marker(uint32_t *pixels, uint32_t width, uint32_t height,
                         uint32_t stride, uint8_t stage);
/* Separate opt-in source-native third-room world-X HUD. Unlike the shared
   magenta marker clamped at player x=210, it directly shows x=0..900.
   Only called for the stage-3 experimental probe, never 1/2-room builds. */
int hm_three_room_progress(uint32_t *pixels, uint32_t width, uint32_t height,
                           uint32_t stride, float world_x);
#endif
