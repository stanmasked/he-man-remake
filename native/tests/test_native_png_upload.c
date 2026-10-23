#include "heman_native_png_upload.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void check_rgb_and_rgba_padding(void) {
    uint8_t src[24], out[80]; hm_texture_reference_binding binding;
    size_t i;
    for (i=0u;i<24u;i+=4u) {
        src[i]=21u; src[i+1u]=31u; src[i+2u]=41u; src[i+3u]=255u;
    }
    memset(out,0xa5,sizeof out); memset(&binding,0,sizeof binding);
    assert(hm_native_png_prepare_rgba(src,sizeof src,3,2,0,1,0,1,7,
        out,sizeof out,&binding)==HM_NATIVE_PNG_UPLOAD_OK);
    assert(binding.width==4u && binding.height==4u && binding.rgba_size==64u);
    assert(binding.rgba==out && binding.texture_slot==7 && binding.filter_mode_code==1);
    assert(binding.wrap_s_code==1 && binding.wrap_t_code==0);
    assert(memcmp(src,out,12u)==0 && memcmp(src+12u,out+16u,12u)==0);
    assert(out[12]==0u && out[13]==0u && out[14]==0u && out[15]==255u);
    for(i=32u;i<64u;i+=4u) assert(out[i]==0u && out[i+3u]==255u);
    for(i=64u;i<sizeof out;++i) assert(out[i]==0xa5u);
    for(i=3u;i<24u;i+=4u) src[i]=128u;
    assert(hm_native_png_prepare_rgba(src,sizeof src,3,2,1,0,1,0,8,
        out,sizeof out,&binding)==HM_NATIVE_PNG_UPLOAD_OK);
    assert(out[12]==0u && out[15]==0u);
    for(i=32u;i<64u;++i) assert(out[i]==0u);
    assert(out[3]==128u && out[19]==128u);
}

static void check_minimum_and_direct(void) {
    const uint8_t src[4]={40,60,80,255};
    uint8_t dest[64]; hm_texture_reference_binding binding; size_t i;
    assert(hm_native_png_prepare_rgba(src,4u,1,1,0,0,0,0,3,
        dest,sizeof dest,&binding)==HM_NATIVE_PNG_UPLOAD_OK);
    assert(binding.width==4u && binding.height==4u);
    assert(memcmp(dest,src,4u)==0);
    for(i=4u;i<64u;i+=4u) assert(dest[i]==0u && dest[i+3u]==255u);
    assert(hm_native_png_prepare_rgba(dest,64u,4,4,0,0,0,0,3,
        dest,sizeof dest,&binding)==HM_NATIVE_PNG_UPLOAD_OK);
    assert(dest[3]==255u && dest[63]==255u);
}

static void check_invalid_input_does_not_write(void) {
    uint8_t src[24], dest[80], prior[80];
    hm_texture_reference_binding binding, before;
    memset(src,0,sizeof src); memset(dest,0xa5,sizeof dest);
    memset(&binding,0x5b,sizeof binding);
    memcpy(prior,dest,sizeof dest); memcpy(&before,&binding,sizeof binding);
#define MUST_REJECT(SIZE,W,H,ALPHA,S,T,F,SLOT,CAP) do { \
    assert(hm_native_png_prepare_rgba(src,(SIZE),(W),(H),(ALPHA),(S),(T),(F),(SLOT), \
            dest,(CAP),&binding)!=HM_NATIVE_PNG_UPLOAD_OK); \
    assert(memcmp(dest,prior,sizeof dest)==0); \
    assert(memcmp(&binding,&before,sizeof before)==0); \
} while(0)
    MUST_REJECT(23u,3u,2u,1,0,0,0,2,sizeof dest);
    MUST_REJECT(24u,3u,2u,0,0,0,0,2,sizeof dest);
    MUST_REJECT(24u,3u,2u,1,0,0,0,2,63u);
    MUST_REJECT(24u,3u,2u,1,2,0,0,2,sizeof dest);
    MUST_REJECT(24u,3u,2u,1,0,0,2,2,sizeof dest);
    MUST_REJECT(24u,3u,2u,1,0,0,0,-1,sizeof dest);
    MUST_REJECT(24u,0u,2u,1,0,0,0,2,sizeof dest);
    MUST_REJECT(24u,32768u,32768u,1,0,0,0,2,sizeof dest);
#undef MUST_REJECT
    assert(hm_native_png_prepare_rgba(NULL,24u,3,2,1,0,0,0,2,
        dest,sizeof dest,&binding)==HM_NATIVE_PNG_UPLOAD_INVALID_ARGUMENT);
    assert(hm_native_png_prepare_rgba(src,24u,3,2,1,0,0,0,2,
        dest,sizeof dest,NULL)==HM_NATIVE_PNG_UPLOAD_INVALID_ARGUMENT);
}

static void check_reference_renderer_accepts_native_binding(void) {
    const uint8_t src[4]={200,80,40,255}, clear[4]={0,0,0,0};
    uint8_t texture[64], framebuffer[64];
    hm_texture_reference_binding binding;
    hm_symbol_frame_packet packet; hm_texture_reference_draw draw;
    hm_texture_reference_projection projection={1,0,0,0,1,0};
    hm_texture_reference_blend blend={HM_GL_ONE,HM_GL_ONE_MINUS_SRC_ALPHA};
    hm_texture_reference_stats stats={0,0};
    memset(&packet,0,sizeof packet);
    assert(hm_native_png_prepare_rgba(src,4u,1u,1u,0,0,0,0,5,
        texture,sizeof texture,&binding)==HM_NATIVE_PNG_UPLOAD_OK);
    packet.source_order=0u; packet.cut_handle=19;
    packet.blend_source=-1; packet.blend_destination=-1;
    packet.xy[0]=0;packet.xy[1]=0;packet.xy[2]=0;packet.xy[3]=4;
    packet.xy[4]=4;packet.xy[5]=4;packet.xy[6]=4;packet.xy[7]=0;
    packet.uv[0]=0;packet.uv[1]=0;packet.uv[2]=0;packet.uv[3]=1;
    packet.uv[4]=1;packet.uv[5]=1;packet.uv[6]=1;packet.uv[7]=0;
    packet.rgba[0]=1;packet.rgba[1]=1;packet.rgba[2]=1;packet.rgba[3]=1;
    draw.packet=&packet;draw.texture_slot=5;
    assert(hm_textured_quad_reference_render(&draw,1,&binding,1,4,4,16,
        &projection,&blend,clear,framebuffer,sizeof framebuffer,&stats)==HM_TEXTURE_REFERENCE_OK);
    assert(memcmp(framebuffer,src,4u)==0);
    assert(framebuffer[4]==0u && framebuffer[7]==255u);
    assert(framebuffer[60]==0u && framebuffer[63]==255u);
    assert(stats.pixel_samples==16u && stats.packets_with_coverage==1u);
}
int main(void) {
    check_rgb_and_rgba_padding(); check_minimum_and_direct();
    check_invalid_input_does_not_write();
    check_reference_renderer_accepts_native_binding();
    puts("Stage224 native padded RGB/RGBA C99 upload/reference tests passed");
    return 0;
}
