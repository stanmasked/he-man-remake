/* Stage209: standalone synthetic textured-quad reference guest.
   No original iOS assets, SpriteCut records or GPU texture upload are used. */
#include <switch.h>
#include <stdint.h>
#include <string.h>
#include "heman_textured_quad_reference.h"
#if defined(HM_NATIVE_PADDING_PROBE)
#include "heman_native_png_upload.h"
#endif

#define FRAME_WIDTH 640u
#define FRAME_HEIGHT 360u
#define TEX_WIDTH 8u
#define TEX_HEIGHT 4u
#define QUAD_LEFT 128u
#define QUAD_TOP 64u
#define QUAD_WIDTH 256u
#define QUAD_HEIGHT 128u

static const uint8_t clear_rgba[4] = {17u, 19u, 23u, 255u};
static const uint8_t palette[4][4] = {
    {255u, 0u, 255u, 255u},   /* magenta */
    {0u, 255u, 0u, 255u},     /* green */
    {0u, 255u, 255u, 255u},   /* cyan */
    {255u, 128u, 0u, 255u}    /* orange */
};
static uint8_t texture_rgba[TEX_WIDTH * TEX_HEIGHT * 4u];
static uint8_t frame_rgba[FRAME_WIDTH * FRAME_HEIGHT * 4u];

static void make_texture(void) {
    uint32_t y, x;
    for (y = 0u; y < TEX_HEIGHT; ++y) {
        for (x = 0u; x < TEX_WIDTH; ++x) {
            const size_t at = ((size_t)y * TEX_WIDTH + x) * 4u;
            const uint32_t color = (x & 1u) | ((y & 1u) << 1u);
            memcpy(texture_rgba + at, palette[color], 4u);
        }
    }
}

static int pixel_is(uint32_t x, uint32_t y, const uint8_t expected[4]) {
    const size_t at = ((size_t)y * FRAME_WIDTH + x) * 4u;
    return memcmp(frame_rgba + at, expected, 4u) == 0;
}

#if defined(HM_NATIVE_PADDING_PROBE)
/* Stage224: asset-free padded upload -> same C99 renderer -> framebuffer.
 * This does not issue real GPU texture uploads. */
static int verify_native_padding_probe(void) {
    const uint8_t src[24]={
        255,0,0,255, 0,255,0,255, 0,0,255,255,
        255,128,0,255, 128,0,255,255, 0,255,255,255
    };
    const uint8_t clear[4]={0,0,0,0};
    uint8_t allocated[64], rendered[64];
    hm_texture_reference_binding binding;
    hm_symbol_frame_packet packet;
    hm_texture_reference_draw draw;
    hm_texture_reference_projection proj={1,0,0,0,1,0};
    hm_texture_reference_blend blend={HM_GL_ONE,HM_GL_ONE_MINUS_SRC_ALPHA};
    hm_texture_reference_stats stats={0u,0u};
    uint32_t x,y;
    if(hm_native_png_prepare_rgba(src,sizeof src,3u,2u,0,0,0,0,42,
          allocated,sizeof allocated,&binding)!=HM_NATIVE_PNG_UPLOAD_OK) return 0;
    if(binding.width!=4u || binding.height!=4u || allocated[15]!=255u ||
       allocated[63]!=255u) return 0;
    memset(&packet,0,sizeof packet);
    packet.source_order=0u;packet.cut_handle=7;packet.blend_source=-1;
    packet.blend_destination=-1;
    packet.xy[0]=0;packet.xy[1]=0;packet.xy[2]=0;packet.xy[3]=4;
    packet.xy[4]=4;packet.xy[5]=4;packet.xy[6]=4;packet.xy[7]=0;
    packet.uv[0]=0;packet.uv[1]=0;packet.uv[2]=0;packet.uv[3]=1;
    packet.uv[4]=1;packet.uv[5]=1;packet.uv[6]=1;packet.uv[7]=0;
    packet.rgba[0]=1;packet.rgba[1]=1;packet.rgba[2]=1;packet.rgba[3]=1;
    draw.packet=&packet;draw.texture_slot=42;
    if(hm_textured_quad_reference_render(&draw,1u,&binding,1u,4u,4u,16u,
        &proj,&blend,clear,rendered,sizeof rendered,&stats)!=HM_TEXTURE_REFERENCE_OK)
        return 0;
    if(memcmp(rendered,allocated,sizeof allocated)!=0 ||
       stats.pixel_samples!=16u || stats.packets_with_coverage!=1u) return 0;
    /* Draw an easily visible 64x64 synthetic texture panel at x16,y16. */
    for(y=0u;y<64u;++y) for(x=0u;x<64u;++x) {
        const size_t dst=(((size_t)y+16u)*FRAME_WIDTH+(size_t)x+16u)*4u;
        const size_t from=(((size_t)y/16u)*4u+(size_t)x/16u)*4u;
        memcpy(frame_rgba+dst,rendered+from,4u);
    }
    return pixel_is(24u,24u,src) &&
           pixel_is(72u,24u,(const uint8_t[4]){0u,0u,0u,255u}) &&
           pixel_is(72u,72u,(const uint8_t[4]){0u,0u,0u,255u});
}
#endif

static int render_and_selfcheck(void) {
    hm_symbol_frame_packet packet;
    hm_texture_reference_draw draw;
    hm_texture_reference_binding binding;
    hm_texture_reference_projection projection = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0};
    hm_texture_reference_blend blend = {HM_GL_ONE, HM_GL_ONE_MINUS_SRC_ALPHA};
    hm_texture_reference_stats stats = {0u, 0u};
    uint32_t x, y;
    hm_texture_reference_status status;

    make_texture();
    memset(&packet, 0, sizeof packet);
    packet.source_order = 0u;
    packet.cut_handle = 9001; /* deliberately different from texture slot */
    packet.front_face_flip = 0;
    packet.xy[0] = (float)QUAD_LEFT;
    packet.xy[1] = (float)QUAD_TOP;
    packet.xy[2] = (float)QUAD_LEFT;
    packet.xy[3] = (float)(QUAD_TOP + QUAD_HEIGHT);
    packet.xy[4] = (float)(QUAD_LEFT + QUAD_WIDTH);
    packet.xy[5] = (float)(QUAD_TOP + QUAD_HEIGHT);
    packet.xy[6] = (float)(QUAD_LEFT + QUAD_WIDTH);
    packet.xy[7] = (float)QUAD_TOP;
    packet.uv[0] = 0.0f; packet.uv[1] = 0.0f;
    packet.uv[2] = 0.0f; packet.uv[3] = 1.0f;
    packet.uv[4] = 1.0f; packet.uv[5] = 1.0f;
    packet.uv[6] = 1.0f; packet.uv[7] = 0.0f;
    packet.rgba[0] = 1.0f; packet.rgba[1] = 1.0f;
    packet.rgba[2] = 1.0f; packet.rgba[3] = 1.0f;
    packet.blend_override_enabled = 0;
    packet.blend_source = -1;
    packet.blend_destination = -1;

    draw.packet = &packet;
    draw.texture_slot = 23;
    binding.texture_slot = 23;
    binding.width = TEX_WIDTH;
    binding.height = TEX_HEIGHT;
    binding.rgba = texture_rgba;
    binding.rgba_size = sizeof texture_rgba;
    binding.wrap_s_code = 0;
    binding.wrap_t_code = 0;
    binding.filter_mode_code = 0;

    status = hm_textured_quad_reference_render(
        &draw, 1u, &binding, 1u, FRAME_WIDTH, FRAME_HEIGHT,
        FRAME_WIDTH * 4u, &projection, &blend, clear_rgba,
        frame_rgba, sizeof frame_rgba, &stats
    );
    if (status != HM_TEXTURE_REFERENCE_OK ||
        stats.packets_with_coverage != 1u ||
        stats.pixel_samples != (size_t)QUAD_WIDTH * QUAD_HEIGHT) {
        return 0;
    }

    for (y = 0u; y < TEX_HEIGHT; ++y) {
        for (x = 0u; x < TEX_WIDTH; ++x) {
            const uint32_t sample_x = QUAD_LEFT + x * (QUAD_WIDTH / TEX_WIDTH)
                                      + (QUAD_WIDTH / TEX_WIDTH) / 2u;
            const uint32_t sample_y = QUAD_TOP + y * (QUAD_HEIGHT / TEX_HEIGHT)
                                      + (QUAD_HEIGHT / TEX_HEIGHT) / 2u;
            const uint32_t color = (x & 1u) | ((y & 1u) << 1u);
            if (!pixel_is(sample_x, sample_y, palette[color])) return 0;
        }
    }
    if (!pixel_is(10u, 10u, clear_rgba) ||
        !pixel_is(QUAD_LEFT + QUAD_WIDTH + 16u,
                  QUAD_TOP + QUAD_HEIGHT + 16u, clear_rgba) ||
        !pixel_is(FRAME_WIDTH - 1u, FRAME_HEIGHT - 1u, clear_rgba)) {
        return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    Framebuffer fb;
    PadState pad;
    Result rc;
    int exit_code = 0;
    (void)argc;
    (void)argv;

    if (!render_and_selfcheck()) return 2;

    memset(&fb, 0, sizeof fb);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);
    rc = framebufferCreate(&fb, nwindowGetDefault(), FRAME_WIDTH, FRAME_HEIGHT,
                           PIXEL_FORMAT_RGBA_8888, 2);
    if (R_FAILED(rc)) return 3;
    rc = framebufferMakeLinear(&fb);
    if (R_FAILED(rc)) {
        framebufferClose(&fb);
        return 4;
    }

    while (appletMainLoop()) {
        uint32_t stride_bytes = 0u;
        uint32_t *pixels;
        uint32_t y;
        padUpdate(&pad);
        if ((padGetButtonsDown(&pad) & HidNpadButton_Plus) != 0u) break;
        pixels = (uint32_t *)framebufferBegin(&fb, &stride_bytes);
        if (pixels == NULL || stride_bytes % sizeof(uint32_t) != 0u ||
            stride_bytes / sizeof(uint32_t) < FRAME_WIDTH) {
            if (pixels != NULL) framebufferEnd(&fb);
            exit_code = 5;
            break;
        }
        for (y = 0u; y < FRAME_HEIGHT; ++y) {
            memcpy((uint8_t *)pixels + (size_t)y * stride_bytes,
                   frame_rgba + (size_t)y * FRAME_WIDTH * 4u,
                   FRAME_WIDTH * 4u);
        }
        framebufferEnd(&fb);
        svcSleepThread(16666667LL);
    }
    framebufferClose(&fb);
    return exit_code;
}
