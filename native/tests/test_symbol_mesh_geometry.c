#include "heman_symbol_mesh_geometry.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static hm_symbol_draw_command make_command(void) {
    hm_symbol_draw_command c;
    memset(&c, 0, sizeof c);
    c.source_order = 3u;
    c.cut_handle = 17;
    c.u0 = -0.25f;
    c.v0 = 0.0f;
    c.u1 = 1.25f;
    c.v1 = 1.0f;
    c.red = 1.0f;
    c.green = 0.5f;
    c.blue = 0.25f;
    c.alpha = 1.0f;
    c.blend_override_enabled = 0;
    c.blend_source = -1;
    c.blend_destination = -1;
    c.symbol_mask = 0;
    c.rotation_degrees = 0.0f;
    c.offset_x = 0.0f;
    c.offset_y = 0.0f;
    c.scale_x = 1.0f;
    c.scale_y = 1.0f;
    return c;
}

static hm_symbol_player_transform identity_player(void) {
    hm_symbol_player_transform t;
    memset(&t, 0, sizeof t);
    t.scale_x = 1.0f;
    t.scale_y = 1.0f;
    return t;
}

static int near(float actual, float expected) {
    return fabsf(actual - expected) <= 0.00002f;
}

static void test_native_vertex_order_and_centered_quad(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_quad_geometry g;
    assert(hm_symbol_mesh_build_quad(&c, 8, 4, NULL, &g) == HM_SYMBOL_MESH_OK);
    assert(g.xy[0] == 0.0f && g.xy[1] == 0.0f);
    assert(g.xy[2] == 0.0f && g.xy[3] == 4.0f);
    assert(g.xy[4] == 8.0f && g.xy[5] == 4.0f);
    assert(g.xy[6] == 8.0f && g.xy[7] == 0.0f);
    assert(g.front_face_flip == 1);
}

static void test_local_scale_then_offset(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_quad_geometry g;
    c.offset_x = 10.0f;
    c.offset_y = 20.0f;
    c.scale_x = 2.0f;
    c.scale_y = 3.0f;
    assert(hm_symbol_mesh_build_quad(&c, 4, 2, NULL, &g) == HM_SYMBOL_MESH_OK);
    assert(g.xy[0] == 8.0f && g.xy[1] == 18.0f);
    assert(g.xy[2] == 8.0f && g.xy[3] == 24.0f);
    assert(g.xy[4] == 16.0f && g.xy[5] == 24.0f);
    assert(g.xy[6] == 16.0f && g.xy[7] == 18.0f);
}

static void test_local_rotation_then_offset(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_quad_geometry g;
    c.rotation_degrees = 90.0f;
    c.offset_x = 3.0f;
    c.offset_y = 4.0f;
    assert(hm_symbol_mesh_build_quad(&c, 2, 2, NULL, &g) == HM_SYMBOL_MESH_OK);
    assert(near(g.xy[0], 5.0f) && near(g.xy[1], 4.0f));
    assert(near(g.xy[2], 3.0f) && near(g.xy[3], 4.0f));
    assert(near(g.xy[4], 3.0f) && near(g.xy[5], 6.0f));
    assert(near(g.xy[6], 5.0f) && near(g.xy[7], 6.0f));
}

static void test_player_transform_order_and_pivots(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_player_transform t = identity_player();
    hm_symbol_quad_geometry g;
    t.rotation_degrees = 90.0f;
    t.rotation_pivot_x = 1.0f;
    t.rotation_pivot_y = 1.0f;
    t.scale_x = 2.0f;
    t.scale_y = 0.5f;
    t.translation_x = 5.0f;
    t.translation_y = 7.0f;
    assert(hm_symbol_mesh_build_quad(&c, 2, 2, &t, &g) == HM_SYMBOL_MESH_OK);
    assert(near(g.xy[0], 9.0f) && near(g.xy[1], 7.0f));
}

static void test_negative_scale_mirrors_and_updates_winding(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_quad_geometry normal, mirrored;
    assert(hm_symbol_mesh_build_quad(&c, 4, 2, NULL, &normal) == HM_SYMBOL_MESH_OK);
    c.scale_x = -1.0f;
    assert(hm_symbol_mesh_build_quad(&c, 4, 2, NULL, &mirrored) == HM_SYMBOL_MESH_OK);
    assert(normal.front_face_flip == 1);
    assert(mirrored.front_face_flip == 0);
    assert(mirrored.xy[0] == 4.0f && mirrored.xy[1] == 0.0f);
}

static void test_player_negative_scale_does_not_recompute_native_winding_flag(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_player_transform t = identity_player();
    hm_symbol_quad_geometry g;
    t.scale_x = -1.0f;
    c.offset_x = 2.0f;
    assert(hm_symbol_mesh_build_quad(&c, 4, 2, &t, &g) == HM_SYMBOL_MESH_OK);
    assert(g.front_face_flip == 1);
    assert(g.xy[0] == -2.0f && g.xy[1] == 0.0f);
}

static void test_signed_dimensions_and_zero_extent_are_preserved(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_quad_geometry zero, negative;
    assert(hm_symbol_mesh_build_quad(&c, 0, 4, NULL, &zero) == HM_SYMBOL_MESH_OK);
    assert(zero.xy[0] == 0.0f && zero.xy[4] == 0.0f);
    assert(hm_symbol_mesh_build_quad(&c, -4, 2, NULL, &negative) == HM_SYMBOL_MESH_OK);
    assert(negative.xy[0] == 0.0f && negative.xy[1] == 0.0f);
    assert(negative.xy[4] == -4.0f && negative.xy[5] == 2.0f);
}

static void test_invalid_inputs_leave_output_unchanged(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_quad_geometry g, before;
    hm_symbol_player_transform t = identity_player();
    memset(&g, 0x5a, sizeof g);
    before = g;
    assert(hm_symbol_mesh_build_quad(NULL, 4, 2, NULL, &g) ==
           HM_SYMBOL_MESH_INVALID_ARGUMENT);
    assert(memcmp(&g, &before, sizeof g) == 0);
    t.scale_y = INFINITY;
    assert(hm_symbol_mesh_build_quad(&c, 4, 2, &t, &g) ==
           HM_SYMBOL_MESH_NONFINITE_TRANSFORM);
    assert(memcmp(&g, &before, sizeof g) == 0);
    c.alpha = NAN;
    assert(hm_symbol_mesh_build_quad(&c, 4, 2, NULL, &g) ==
           HM_SYMBOL_MESH_INVALID_DRAW_COMMAND);
    assert(memcmp(&g, &before, sizeof g) == 0);
}

static void test_geometry_overflow_fails_closed(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_quad_geometry g;
    c.scale_x = 3.0e38f;
    assert(hm_symbol_mesh_build_quad(&c, 2000000000, 2, NULL, &g) ==
           HM_SYMBOL_MESH_NONFINITE_GEOMETRY);
}

static void test_uvs_are_not_clipped_or_modified(void) {
    hm_symbol_draw_command c = make_command();
    hm_symbol_quad_geometry g;
    assert(hm_symbol_mesh_build_quad(&c, 3, 5, NULL, &g) == HM_SYMBOL_MESH_OK);
    assert(c.u0 == -0.25f && c.u1 == 1.25f);
}

int main(void) {
    test_native_vertex_order_and_centered_quad();
    test_local_scale_then_offset();
    test_local_rotation_then_offset();
    test_player_transform_order_and_pivots();
    test_negative_scale_mirrors_and_updates_winding();
    test_player_negative_scale_does_not_recompute_native_winding_flag();
    test_signed_dimensions_and_zero_extent_are_preserved();
    test_invalid_inputs_leave_output_unchanged();
    test_geometry_overflow_fails_closed();
    test_uvs_are_not_clipped_or_modified();
    puts("Stage199 C99 Symbol mesh geometry tests passed");
    return 0;
}
