#ifndef HEMAN_SYMBOL_MESH_GEOMETRY_H
#define HEMAN_SYMBOL_MESH_GEOMETRY_H

#include "heman_symbol_draw_plan.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct hm_symbol_player_transform {
    float rotation_degrees;
    float rotation_pivot_x;
    float rotation_pivot_y;
    float scale_x;
    float scale_y;
    float scale_pivot_x;
    float scale_pivot_y;
    float translation_x;
    float translation_y;
} hm_symbol_player_transform;

/*
 * Portable geometry result. xy stores four 2D vertices in the original
 * GL_TRIANGLE_FAN source order:
 *   (-halfW,-halfH), (-halfW,+halfH), (+halfW,+halfH), (+halfW,-halfH)
 * after transforms. UVs remain on the draw command and are not clipped.
 */
typedef struct hm_symbol_quad_geometry {
    int32_t front_face_flip;
    float xy[8];
} hm_symbol_quad_geometry;

typedef enum hm_symbol_mesh_status {
    HM_SYMBOL_MESH_OK = 0,
    HM_SYMBOL_MESH_INVALID_ARGUMENT = 1,
    HM_SYMBOL_MESH_INVALID_DRAW_COMMAND = 2,
    HM_SYMBOL_MESH_NONFINITE_TRANSFORM = 3,
    HM_SYMBOL_MESH_NONFINITE_GEOMETRY = 4
} hm_symbol_mesh_status;

/*
 * Expand the four native SpriteCut UV endpoints into the same vertex order as
 * the XY fan: (u0,v0), (u0,v1), (u1,v1), (u1,v0). Values outside [0,1] are
 * preserved. out_uv receives eight binary32 values only on success.
 */
hm_symbol_mesh_status hm_symbol_mesh_expand_uvs(
    const hm_symbol_draw_command *command,
    float out_uv[8]
);

/*
 * Build a centered quad from the original signed SpriteCut width/height.
 * Serialized Symbol offsets locate the unscaled top-left corner. Native local
 * points are scaled and rotated around the origin, then translated by
 * (offset_x + cut_width/2, offset_y + cut_height/2).
 * SpritePlayer transform order: rotate about pivot -> scale about pivot ->
 * translation. The player transform may be NULL to request identity.
 *
 * Zero and negative cut dimensions/scales are preserved as native geometry
 * semantics; no crop, clipping, UV rewrite, or GPU call occurs. Output is
 * written only on success.
 */
hm_symbol_mesh_status hm_symbol_mesh_build_quad(
    const hm_symbol_draw_command *command,
    int32_t cut_width,
    int32_t cut_height,
    const hm_symbol_player_transform *player_transform,
    hm_symbol_quad_geometry *out_geometry
);

#ifdef __cplusplus
}
#endif

#endif
