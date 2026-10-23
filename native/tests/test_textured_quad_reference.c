#include "heman_textured_quad_reference.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static hm_symbol_frame_packet packet(uint32_t order,int32_t handle) {
    hm_symbol_frame_packet p; memset(&p,0,sizeof p);
    p.source_order=order; p.cut_handle=handle; p.front_face_flip=0;
    p.xy[0]=0; p.xy[1]=0; p.xy[2]=0; p.xy[3]=2;
    p.xy[4]=2; p.xy[5]=2; p.xy[6]=2; p.xy[7]=0;
    p.uv[0]=0; p.uv[1]=0; p.uv[2]=0; p.uv[3]=1;
    p.uv[4]=1; p.uv[5]=1; p.uv[6]=1; p.uv[7]=0;
    p.rgba[0]=1; p.rgba[1]=1; p.rgba[2]=1; p.rgba[3]=1;
    p.blend_override_enabled=0; p.blend_source=-1; p.blend_destination=-1;
    return p;
}
static hm_texture_reference_projection projection_identity(void) {
    hm_texture_reference_projection p={1,0,0,0,1,0}; return p;
}
static hm_texture_reference_blend blend_default(void) {
    hm_texture_reference_blend b={HM_GL_ONE,HM_GL_ONE_MINUS_SRC_ALPHA}; return b;
}
static void unit_quad(hm_symbol_frame_packet *p) {
    p->xy[2]=0; p->xy[3]=1; p->xy[4]=1; p->xy[5]=1; p->xy[6]=1; p->xy[7]=0;
}
static void test_nearest_and_row_padding(void) {
    const uint8_t tex[16]={255,0,0,255,0,255,0,255,0,0,255,255,255,255,255,255};
    const uint8_t clear[4]={0,0,0,0};
    hm_symbol_frame_packet p=packet(0,12);
    hm_texture_reference_draw draw={&p,4};
    hm_texture_reference_binding binding={4,2,2,tex,sizeof tex,0,0,0};
    hm_texture_reference_projection proj=projection_identity();
    hm_texture_reference_blend blend=blend_default();
    hm_texture_reference_stats stats={88,99}; uint8_t out[24];
    memset(out,0xa5,sizeof out);
    assert(hm_textured_quad_reference_render(&draw,1,&binding,1,2,2,12,&proj,&blend,
        clear,out,sizeof out,&stats)==HM_TEXTURE_REFERENCE_OK);
    assert(memcmp(out,tex,8)==0 && memcmp(out+12,tex+8,8)==0);
    assert(out[8]==0xa5 && out[11]==0xa5 && out[20]==0xa5 && out[23]==0xa5);
    assert(stats.packets_with_coverage==1 && stats.pixel_samples==4);
}
static void test_negative_u_repeat_uses_explicit_slot(void) {
    const uint8_t tex[8]={255,0,0,255,0,255,0,255},clear[4]={0,0,0,0};
    const uint8_t expected[8]={0,255,0,255,255,0,0,255};
    hm_symbol_frame_packet p=packet(0,17);
    hm_texture_reference_draw draw={&p,6};
    hm_texture_reference_binding binding={6,2,1,tex,sizeof tex,1,0,0};
    hm_texture_reference_projection proj=projection_identity();
    hm_texture_reference_blend blend=blend_default();
    hm_texture_reference_stats stats={0,0}; uint8_t out[8]={0};
    p.xy[3]=1; p.xy[4]=2; p.xy[5]=1;
    p.uv[0]=-.5f; p.uv[2]=-.5f; p.uv[4]=.5f; p.uv[6]=.5f;
    assert(hm_textured_quad_reference_render(&draw,1,&binding,1,2,1,8,&proj,&blend,
        clear,out,sizeof out,&stats)==HM_TEXTURE_REFERENCE_OK);
    assert(memcmp(out,expected,sizeof out)==0 && stats.pixel_samples==2);
}
static void test_blend_and_symbol_override(void) {
    const uint8_t tex[4]={128,0,0,128},clear[4]={0,0,255,255};
    const uint8_t expected[4]={128,0,127,255},override_expected[4]={128,0,255,255};
    hm_symbol_frame_packet p=packet(0,2); hm_texture_reference_draw draw={&p,3};
    hm_texture_reference_binding binding={3,1,1,tex,sizeof tex,0,0,0};
    hm_texture_reference_projection proj=projection_identity();
    hm_texture_reference_blend blend=blend_default();
    hm_texture_reference_stats stats={0,0}; uint8_t out[4]={0};
    unit_quad(&p);
    assert(hm_textured_quad_reference_render(&draw,1,&binding,1,1,1,4,&proj,&blend,
        clear,out,sizeof out,&stats)==HM_TEXTURE_REFERENCE_OK);
    assert(memcmp(out,expected,4)==0);
    p.blend_override_enabled=1; p.blend_source=(int32_t)HM_GL_ONE;
    p.blend_destination=(int32_t)HM_GL_ONE;
    assert(hm_textured_quad_reference_render(&draw,1,&binding,1,1,1,4,&proj,&blend,
        clear,out,sizeof out,&stats)==HM_TEXTURE_REFERENCE_OK);
    assert(memcmp(out,override_expected,4)==0);
}
static void test_projection_translation(void) {
    const uint8_t tex[4]={255,255,255,255},clear[4]={0,0,0,0};
    const uint8_t expected[8]={0,0,0,0,255,255,255,255};
    hm_symbol_frame_packet p=packet(0,2); hm_texture_reference_draw draw={&p,1};
    hm_texture_reference_binding binding={1,1,1,tex,sizeof tex,0,0,0};
    hm_texture_reference_projection proj={1,0,1,0,1,0};
    hm_texture_reference_blend blend=blend_default();
    hm_texture_reference_stats stats={0,0}; uint8_t out[8]={0};
    unit_quad(&p);
    assert(hm_textured_quad_reference_render(&draw,1,&binding,1,2,1,8,&proj,&blend,
        clear,out,sizeof out,&stats)==HM_TEXTURE_REFERENCE_OK);
    assert(memcmp(out,expected,sizeof out)==0);
}
static void test_failure_is_transactional(void) {
    const uint8_t tex[4]={255,255,255,255},clear[4]={0,0,0,0};
    hm_symbol_frame_packet p=packet(0,2); hm_texture_reference_draw draw={&p,1};
    hm_texture_reference_binding binding={1,1,1,tex,sizeof tex,0,0,0};
    hm_texture_reference_projection proj=projection_identity();
    hm_texture_reference_blend blend=blend_default();
    hm_texture_reference_stats stats={77,88}; uint8_t out[4],before[4];
    unit_quad(&p); p.xy[4]=2.5f; memset(out,0xa5,sizeof out); memcpy(before,out,4);
    assert(hm_textured_quad_reference_render(&draw,1,&binding,1,1,1,4,&proj,&blend,
        clear,out,sizeof out,&stats)==HM_TEXTURE_REFERENCE_NON_AFFINE_QUAD);
    assert(memcmp(out,before,4)==0 && stats.packets_with_coverage==77 && stats.pixel_samples==88);
}
static void test_missing_slot_fails_closed(void) {
    const uint8_t clear[4]={0,0,0,0};
    hm_symbol_frame_packet p=packet(0,2); hm_texture_reference_draw draw={&p,-1};
    hm_texture_reference_projection proj=projection_identity();
    hm_texture_reference_blend blend=blend_default();
    hm_texture_reference_stats stats={0,0}; uint8_t out[16]; memset(out,0x4c,sizeof out);
    assert(hm_textured_quad_reference_render(&draw,1,NULL,0,2,2,8,&proj,&blend,
        clear,out,sizeof out,&stats)==HM_TEXTURE_REFERENCE_INVALID_PACKET);
    assert(out[0]==0x4c && out[15]==0x4c);
}
static void test_empty_frame_clears(void) {
    const uint8_t clear[4]={1,2,3,4},expected[8]={1,2,3,4,1,2,3,4};
    hm_texture_reference_projection proj=projection_identity();
    hm_texture_reference_blend blend=blend_default();
    hm_texture_reference_stats stats={9,10}; uint8_t out[8]={0};
    assert(hm_textured_quad_reference_render(NULL,0,NULL,0,2,1,8,&proj,&blend,
        clear,out,sizeof out,&stats)==HM_TEXTURE_REFERENCE_OK);
    assert(memcmp(out,expected,8)==0 && stats.packets_with_coverage==0 && stats.pixel_samples==0);
}
int main(void) {
    test_nearest_and_row_padding(); test_negative_u_repeat_uses_explicit_slot();
    test_blend_and_symbol_override(); test_projection_translation();
    test_failure_is_transactional(); test_missing_slot_fails_closed(); test_empty_frame_clears();
    puts("Stage208 textured quad C99 reference tests passed");
    return 0;
}
