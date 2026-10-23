#include "heman_symbol_frame_assembler.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static hm_symbol_draw_command make_command(uint32_t order, int32_t handle) {
    hm_symbol_draw_command c;
    memset(&c, 0, sizeof c);
    c.source_order = order;
    c.cut_handle = handle;
    c.u0 = -0.25f;
    c.v0 = 0.125f;
    c.u1 = 1.25f;
    c.v1 = 0.875f;
    c.red = 1.0f;
    c.green = 0.5f;
    c.blue = 0.25f;
    c.alpha = 0.75f;
    c.blend_override_enabled = 0;
    c.blend_source = -1;
    c.blend_destination = -1;
    c.symbol_mask = 0;
    c.rotation_degrees = 0.0f;
    c.offset_x = 10.0f;
    c.offset_y = 20.0f;
    c.scale_x = 1.0f;
    c.scale_y = 1.0f;
    return c;
}

static void test_assembles_source_order_geometry_uv_color_and_blend(void) {
    hm_symbol_draw_command commands[3];
    hm_symbol_cut_extent extents[3] = {{8, 4}, {4, 2}, {3, 5}};
    hm_symbol_frame_packet packets[3];
    size_t packet_count = 99u;

    commands[0] = make_command(0u, 17);
    commands[1] = make_command(1u, 18);
    commands[2] = make_command(2u, 19);
    commands[1].symbol_mask = 4;

    assert(hm_symbol_frame_assemble(
        commands, extents, 3u, 4, NULL, packets, 3u, &packet_count
    ) == HM_SYMBOL_FRAME_OK);
    assert(packet_count == 2u);
    assert(packets[0].source_order == 0u);
    assert(packets[0].cut_handle == 17);
    assert(packets[1].source_order == 2u);
    assert(packets[1].cut_handle == 19);

    /* The native offset is the unscaled top-left corner. */
    assert(packets[0].xy[0] == 10.0f && packets[0].xy[1] == 20.0f);
    assert(packets[0].xy[2] == 10.0f && packets[0].xy[3] == 24.0f);
    assert(packets[0].xy[4] == 18.0f && packets[0].xy[5] == 24.0f);
    assert(packets[0].xy[6] == 18.0f && packets[0].xy[7] == 20.0f);
    assert(packets[0].front_face_flip == 1);

    assert(packets[0].uv[0] == -0.25f && packets[0].uv[1] == 0.125f);
    assert(packets[0].uv[2] == -0.25f && packets[0].uv[3] == 0.875f);
    assert(packets[0].uv[4] == 1.25f && packets[0].uv[5] == 0.875f);
    assert(packets[0].uv[6] == 1.25f && packets[0].uv[7] == 0.125f);
    assert(packets[0].rgba[0] == 1.0f);
    assert(packets[0].rgba[1] == 0.5f);
    assert(packets[0].rgba[2] == 0.25f);
    assert(packets[0].rgba[3] == 0.75f);
    assert(packets[0].blend_override_enabled == 0);
    assert(packets[0].blend_source == -1 && packets[0].blend_destination == -1);
}

static void test_insufficient_capacity_leaves_all_outputs_unchanged(void) {
    hm_symbol_draw_command commands[2] = {
        make_command(0u, 17), make_command(1u, 18)
    };
    hm_symbol_cut_extent extents[2] = {{8, 4}, {4, 2}};
    hm_symbol_frame_packet packets[2], before[2];
    size_t packet_count = 99u;
    memset(packets, 0x5a, sizeof packets);
    memcpy(before, packets, sizeof packets);

    assert(hm_symbol_frame_assemble(
        commands, extents, 2u, 0, NULL, packets, 1u, &packet_count
    ) == HM_SYMBOL_FRAME_OUTPUT_TOO_SMALL);
    assert(packet_count == 99u);
    assert(memcmp(packets, before, sizeof packets) == 0);
}

static void test_invalid_late_command_does_not_commit_partial_frame(void) {
    hm_symbol_draw_command commands[2] = {
        make_command(0u, 17), make_command(1u, 18)
    };
    hm_symbol_cut_extent extents[2] = {{8, 4}, {4, 2}};
    hm_symbol_frame_packet packets[2], before[2];
    size_t packet_count = 55u;
    commands[1].alpha = NAN;
    memset(packets, 0x3c, sizeof packets);
    memcpy(before, packets, sizeof packets);

    assert(hm_symbol_frame_assemble(
        commands, extents, 2u, 0, NULL, packets, 2u, &packet_count
    ) == HM_SYMBOL_FRAME_INVALID_DRAW_PLAN);
    assert(packet_count == 55u);
    assert(memcmp(packets, before, sizeof packets) == 0);
}

static void test_invalid_transform_rejected_even_when_every_symbol_is_masked(void) {
    hm_symbol_draw_command command = make_command(0u, 17);
    hm_symbol_cut_extent extent = {8, 4};
    hm_symbol_player_transform transform;
    hm_symbol_frame_packet packet;
    size_t packet_count = 44u;
    memset(&transform, 0, sizeof transform);
    transform.scale_x = NAN;
    transform.scale_y = 1.0f;
    command.symbol_mask = 4;

    assert(hm_symbol_frame_assemble(
        &command, &extent, 1u, 4, &transform, &packet, 1u, &packet_count
    ) == HM_SYMBOL_FRAME_INVALID_TRANSFORM);
    assert(packet_count == 44u);
}

static void test_geometry_overflow_fails_without_output_commit(void) {
    hm_symbol_draw_command command = make_command(0u, 17);
    hm_symbol_cut_extent extent = {2000000000, 2};
    hm_symbol_frame_packet packet, before;
    size_t packet_count = 66u;
    command.scale_x = 3.0e38f;
    memset(&packet, 0x69, sizeof packet);
    before = packet;

    assert(hm_symbol_frame_assemble(
        &command, &extent, 1u, 0, NULL, &packet, 1u, &packet_count
    ) == HM_SYMBOL_FRAME_GEOMETRY_FAILED);
    assert(packet_count == 66u);
    assert(memcmp(&packet, &before, sizeof packet) == 0);
}

static void test_command_bound_and_empty_frame(void) {
    size_t packet_count = 77u;
    assert(hm_symbol_frame_assemble(
        NULL, NULL, (size_t)HM_SYMBOL_FRAME_MAX_COMMANDS + 1u,
        0, NULL, NULL, 0u, &packet_count
    ) == HM_SYMBOL_FRAME_TOO_MANY_COMMANDS);
    assert(packet_count == 77u);

    assert(hm_symbol_frame_assemble(
        NULL, NULL, 0u, 0, NULL, NULL, 0u, &packet_count
    ) == HM_SYMBOL_FRAME_OK);
    assert(packet_count == 0u);
}

static void test_required_arguments_are_checked(void) {
    hm_symbol_draw_command command = make_command(0u, 17);
    hm_symbol_cut_extent extent = {8, 4};
    hm_symbol_frame_packet packet;
    size_t packet_count = 88u;
    assert(hm_symbol_frame_assemble(
        &command, &extent, 1u, 0, NULL, &packet, 1u, NULL
    ) == HM_SYMBOL_FRAME_INVALID_ARGUMENT);
    assert(hm_symbol_frame_assemble(
        NULL, &extent, 1u, 0, NULL, &packet, 1u, &packet_count
    ) == HM_SYMBOL_FRAME_INVALID_ARGUMENT);
    assert(packet_count == 88u);
}

int main(void) {
    test_assembles_source_order_geometry_uv_color_and_blend();
    test_insufficient_capacity_leaves_all_outputs_unchanged();
    test_invalid_late_command_does_not_commit_partial_frame();
    test_invalid_transform_rejected_even_when_every_symbol_is_masked();
    test_geometry_overflow_fails_without_output_commit();
    test_command_bound_and_empty_frame();
    test_required_arguments_are_checked();
    puts("Stage201 bounded native frame assembler tests passed");
    return 0;
}
