#include "heman_symbol_frame_assembler.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

static int hm_frame_transform_finite(const hm_symbol_player_transform *t) {
    return t == NULL ||
           (isfinite(t->rotation_degrees) &&
            isfinite(t->rotation_pivot_x) &&
            isfinite(t->rotation_pivot_y) &&
            isfinite(t->scale_x) && isfinite(t->scale_y) &&
            isfinite(t->scale_pivot_x) &&
            isfinite(t->scale_pivot_y) &&
            isfinite(t->translation_x) &&
            isfinite(t->translation_y));
}

hm_symbol_frame_status hm_symbol_frame_assemble(
    const hm_symbol_draw_command *commands,
    const hm_symbol_cut_extent *cut_extents,
    size_t count,
    int32_t active_mask,
    const hm_symbol_player_transform *player_transform,
    hm_symbol_frame_packet *out_packets,
    size_t output_capacity,
    size_t *output_count
) {
    hm_symbol_frame_packet *staged = NULL;
    size_t drawable_count = 0u;
    size_t written = 0u;
    size_t i;

    if (output_count == NULL) {
        return HM_SYMBOL_FRAME_INVALID_ARGUMENT;
    }
    if (count > (size_t)HM_SYMBOL_FRAME_MAX_COMMANDS) {
        return HM_SYMBOL_FRAME_TOO_MANY_COMMANDS;
    }
    if (count != 0u && (commands == NULL || cut_extents == NULL)) {
        return HM_SYMBOL_FRAME_INVALID_ARGUMENT;
    }
    if (!hm_frame_transform_finite(player_transform)) {
        return HM_SYMBOL_FRAME_INVALID_TRANSFORM;
    }
    if (hm_symbol_draw_plan_validate(commands, count) != HM_SYMBOL_DRAW_PLAN_OK) {
        return HM_SYMBOL_FRAME_INVALID_DRAW_PLAN;
    }

    for (i = 0u; i < count; ++i) {
        if ((commands[i].symbol_mask & active_mask) == 0) {
            ++drawable_count;
        }
    }
    if (drawable_count > output_capacity) {
        return HM_SYMBOL_FRAME_OUTPUT_TOO_SMALL;
    }
    if (drawable_count != 0u && out_packets == NULL) {
        return HM_SYMBOL_FRAME_INVALID_ARGUMENT;
    }

    if (drawable_count != 0u) {
        staged = (hm_symbol_frame_packet *)malloc(
            drawable_count * sizeof(*staged)
        );
        if (staged == NULL) {
            return HM_SYMBOL_FRAME_ALLOCATION_FAILED;
        }
    }

    for (i = 0u; i < count; ++i) {
        const hm_symbol_draw_command *command = &commands[i];
        hm_symbol_quad_geometry geometry;
        hm_symbol_frame_packet packet;
        hm_symbol_mesh_status mesh_status;
        size_t channel;

        if ((command->symbol_mask & active_mask) != 0) {
            continue;
        }

        mesh_status = hm_symbol_mesh_build_quad(
            command, cut_extents[i].width, cut_extents[i].height,
            player_transform, &geometry
        );
        if (mesh_status != HM_SYMBOL_MESH_OK) {
            free(staged);
            return HM_SYMBOL_FRAME_GEOMETRY_FAILED;
        }
        mesh_status = hm_symbol_mesh_expand_uvs(command, packet.uv);
        if (mesh_status != HM_SYMBOL_MESH_OK) {
            free(staged);
            return HM_SYMBOL_FRAME_UV_FAILED;
        }

        packet.source_order = command->source_order;
        packet.cut_handle = command->cut_handle;
        packet.front_face_flip = geometry.front_face_flip;
        memcpy(packet.xy, geometry.xy, sizeof packet.xy);
        packet.rgba[0] = command->red;
        packet.rgba[1] = command->green;
        packet.rgba[2] = command->blue;
        packet.rgba[3] = command->alpha;
        packet.blend_override_enabled = command->blend_override_enabled;
        packet.blend_source = command->blend_source;
        packet.blend_destination = command->blend_destination;
        /* Keep this loop explicit so every output field is initialized. */
        for (channel = 0u; channel < 4u; ++channel) {
            if (!isfinite(packet.rgba[channel])) {
                free(staged);
                return HM_SYMBOL_FRAME_INVALID_DRAW_PLAN;
            }
        }
        staged[written++] = packet;
    }

    if (written != drawable_count) {
        free(staged);
        return HM_SYMBOL_FRAME_INVALID_DRAW_PLAN;
    }
    if (written != 0u) {
        memmove(out_packets, staged, written * sizeof(*staged));
    }
    free(staged);
    *output_count = written;
    return HM_SYMBOL_FRAME_OK;
}
