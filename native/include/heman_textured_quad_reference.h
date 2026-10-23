#ifndef HEMAN_TEXTURED_QUAD_REFERENCE_H
#define HEMAN_TEXTURED_QUAD_REFERENCE_H
#include "heman_symbol_frame_assembler.h"
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define HM_TEXTURE_REF_MAX_PACKETS 1024u
#define HM_TEXTURE_REF_MAX_BINDINGS 4096u
#define HM_TEXTURE_REF_MAX_TEXTURE_BYTES (64u*1024u*1024u)
#define HM_TEXTURE_REF_MAX_FRAME_PIXELS 4194304u
#define HM_TEXTURE_REF_MAX_SAMPLE_ATTEMPTS 16777216u
#define HM_GL_ZERO 0u
#define HM_GL_ONE 1u
#define HM_GL_SRC_COLOR 0x0300u
#define HM_GL_ONE_MINUS_SRC_COLOR 0x0301u
#define HM_GL_SRC_ALPHA 0x0302u
#define HM_GL_ONE_MINUS_SRC_ALPHA 0x0303u
#define HM_GL_DST_ALPHA 0x0304u
#define HM_GL_ONE_MINUS_DST_ALPHA 0x0305u
#define HM_GL_DST_COLOR 0x0306u
#define HM_GL_ONE_MINUS_DST_COLOR 0x0307u
#define HM_GL_SRC_ALPHA_SATURATE 0x0308u

typedef struct hm_texture_reference_draw {
    const hm_symbol_frame_packet *packet;
    int32_t texture_slot;
} hm_texture_reference_draw;

typedef struct hm_texture_reference_binding {
    int32_t texture_slot;
    uint32_t width, height;
    const uint8_t *rgba;
    size_t rgba_size;
    int32_t wrap_s_code, wrap_t_code, filter_mode_code;
} hm_texture_reference_binding;

typedef struct hm_texture_reference_projection {
    double m00, m01, tx, m10, m11, ty;
} hm_texture_reference_projection;

typedef struct hm_texture_reference_blend {
    uint32_t source_factor, destination_factor;
} hm_texture_reference_blend;

typedef struct hm_texture_reference_stats {
    size_t packets_with_coverage, pixel_samples;
} hm_texture_reference_stats;

typedef enum hm_texture_reference_status {
    HM_TEXTURE_REFERENCE_OK = 0,
    HM_TEXTURE_REFERENCE_INVALID_ARGUMENT = 1,
    HM_TEXTURE_REFERENCE_LIMIT_EXCEEDED = 2,
    HM_TEXTURE_REFERENCE_INVALID_PACKET = 3,
    HM_TEXTURE_REFERENCE_INVALID_TEXTURE = 4,
    HM_TEXTURE_REFERENCE_MISSING_TEXTURE = 5,
    HM_TEXTURE_REFERENCE_INVALID_STATE = 6,
    HM_TEXTURE_REFERENCE_NONFINITE = 7,
    HM_TEXTURE_REFERENCE_NON_AFFINE_QUAD = 8,
    HM_TEXTURE_REFERENCE_ALLOCATION_FAILED = 9
} hm_texture_reference_status;

/* CPU reference only. Each draw pairs a Stage201 packet with an explicitly
 * resolved non-negative texture slot; cut_handle is not texture identity.
 * Projection is separate, output is top-left-origin RGBA, and texture bytes
 * are used as supplied (no row flip or extra premultiplication). On failure,
 * output pixels, row padding, and stats are left untouched.
 */
hm_texture_reference_status hm_textured_quad_reference_render(
    const hm_texture_reference_draw *draws, size_t draw_count,
    const hm_texture_reference_binding *bindings, size_t binding_count,
    uint32_t width, uint32_t height, size_t stride_bytes,
    const hm_texture_reference_projection *projection,
    const hm_texture_reference_blend *frame_blend,
    const uint8_t clear_rgba[4], uint8_t *out_pixels, size_t out_capacity,
    hm_texture_reference_stats *out_stats
);
#ifdef __cplusplus
}
#endif
#endif
