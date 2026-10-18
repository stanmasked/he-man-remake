#ifndef HEMAN_RASTER_SCENE_H
#define HEMAN_RASTER_SCENE_H

#include <stdint.h>
#include "heman_session.h"

/* Independent asset-free raster test scene, not original He-Man artwork.
   Fixed 640x360 RGBA8888 output. Stride is in 32-bit pixels. */
#define HM_RASTER_WIDTH 640u
#define HM_RASTER_HEIGHT 360u
typedef struct {
    const hm_world *world;
    const hm_session *game;
    const hm_combat_config *combat;
    uint8_t qa_state; /* 0=ready, 1=passed, 2=failed */
    uint32_t qa_fingerprint;
} hm_raster_view;

/* Fail closed on invalid parameters, leaving output unchanged. Caller
   guarantees borrowed state and tile arrays stay alive throughout call. */
int hm_raster_render(uint32_t *pixels, uint32_t width, uint32_t height,
                     uint32_t stride, const hm_raster_view *view);
#endif
