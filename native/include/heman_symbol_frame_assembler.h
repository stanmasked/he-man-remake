#ifndef HEMAN_SYMBOL_FRAME_ASSEMBLER_H
#define HEMAN_SYMBOL_FRAME_ASSEMBLER_H

#include "heman_symbol_mesh_geometry.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Defensive limit for a single assembled frame. This is an implementation
 * bound, not a claim about the original game's maximum Symbol count.
 */
#define HM_SYMBOL_FRAME_MAX_COMMANDS 1024u

typedef struct hm_symbol_cut_extent {
    int32_t width;
    int32_t height;
} hm_symbol_cut_extent;

typedef struct hm_symbol_frame_packet {
    uint32_t source_order;
    int32_t cut_handle;
    int32_t front_face_flip;
    float xy[8];
    float uv[8];
    float rgba[4];
    int32_t blend_override_enabled;
    int32_t blend_source;
    int32_t blend_destination;
} hm_symbol_frame_packet;

typedef enum hm_symbol_frame_status {
    HM_SYMBOL_FRAME_OK = 0,
    HM_SYMBOL_FRAME_INVALID_ARGUMENT = 1,
    HM_SYMBOL_FRAME_TOO_MANY_COMMANDS = 2,
    HM_SYMBOL_FRAME_INVALID_DRAW_PLAN = 3,
    HM_SYMBOL_FRAME_OUTPUT_TOO_SMALL = 4,
    HM_SYMBOL_FRAME_INVALID_TRANSFORM = 5,
    HM_SYMBOL_FRAME_GEOMETRY_FAILED = 6,
    HM_SYMBOL_FRAME_UV_FAILED = 7,
    HM_SYMBOL_FRAME_ALLOCATION_FAILED = 8
} hm_symbol_frame_status;

/*
 * Assemble an ordered, asset-resolved frame into renderer-ready CPU packets.
 *
 * commands and cut_extents are parallel arrays, one entry per original
 * Symbol, including masked Symbols. The complete command list is validated
 * before work begins. Entries for which (symbol_mask & active_mask) != 0
 * are omitted, while surviving source_order values remain unchanged.
 *
 * Each packet contains transformed XY, native UV corner order, RGBA, blend
 * metadata, cut handle and the native pre-player-transform winding flag.
 * No GPU calls, texture binding, allocation of original resources, or pixel
 * rendering occurs here.
 *
 * The result is transactional: output packets and output_count are unchanged
 * on every failure. The caller must supply output capacity for all drawable
 * entries. A NULL output buffer is permitted only when zero entries are drawn.
 * count is bounded by HM_SYMBOL_FRAME_MAX_COMMANDS; the bound is defensive,
 * not a statement of the original game's actual maximum.
 */
hm_symbol_frame_status hm_symbol_frame_assemble(
    const hm_symbol_draw_command *commands,
    const hm_symbol_cut_extent *cut_extents,
    size_t count,
    int32_t active_mask,
    const hm_symbol_player_transform *player_transform,
    hm_symbol_frame_packet *out_packets,
    size_t output_capacity,
    size_t *output_count
);

#ifdef __cplusplus
}
#endif

#endif
