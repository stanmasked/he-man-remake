/* Portable, deterministic RGBA8888 synthetic scene for a native Switch
   framebuffer. No images, fonts, shaders or copyrighted game data. */
#include "raster_scene.h"
#include <math.h>
#include <stddef.h>

static void rect(uint32_t *pixels, uint32_t stride,
                 int x, int y, int w, int h, uint32_t color) {
    int row, col, x1 = x + w, y1 = y + h;
    if (w <= 0 || h <= 0 || x >= (int)HM_RASTER_WIDTH ||
        y >= (int)HM_RASTER_HEIGHT || x1 <= 0 || y1 <= 0)
        return;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x1 > (int)HM_RASTER_WIDTH) x1 = (int)HM_RASTER_WIDTH;
    if (y1 > (int)HM_RASTER_HEIGHT) y1 = (int)HM_RASTER_HEIGHT;
    for (row = y; row < y1; ++row)
        for (col = x; col < x1; ++col)
            pixels[(uint32_t)row * stride + (uint32_t)col] = color;
}

static void disk(uint32_t *pixels, uint32_t stride, int cx, int cy,
                 int radius, uint32_t color) {
    int y, x;
    if (cx < -radius || cy < -radius ||
        cx >= (int)HM_RASTER_WIDTH + radius ||
        cy >= (int)HM_RASTER_HEIGHT + radius) return;
    for (y = -radius; y <= radius; ++y) {
        int yy = cy + y;
        if (yy < 0 || yy >= (int)HM_RASTER_HEIGHT) continue;
        for (x = -radius; x <= radius; ++x) {
            int xx = cx + x;
            if (xx < 0 || xx >= (int)HM_RASTER_WIDTH) continue;
            if (x*x + y*y <= radius*radius)
                pixels[(uint32_t)yy * stride + (uint32_t)xx] = color;
        }
    }
}

/* Fifteen 0/1 cells each: compact original 3x5 hexadecimal display. */
static const char *const hex3x5[16] = {
    "111101101101111", "010110010010111", "111001111100111",
    "111001111001111", "101101111001001", "111100111001111",
    "111100111101111", "111001001001001", "111101111101111",
    "111101111001111", "111101111101101", "110101110101110",
    "111100100100111", "110101101101110", "111100110100111",
    "111100110100100"
};
static void hex_score(uint32_t *pixels, uint32_t stride, uint32_t value,
                      int left, int top, uint32_t color) {
    unsigned digit, bit, row, col;
    for (digit = 0u; digit < 8u; ++digit) {
        const unsigned nibble = (unsigned)((value >> (28u-4u*digit)) & 15u);
        const char *glyph = hex3x5[nibble];
        for (row = 0u; row < 5u; ++row)
            for (col = 0u; col < 3u; ++col) {
                bit = row*3u + col;
                if (glyph[bit] == '1')
                    rect(pixels,stride,left+(int)(digit*15u+col*3u),
                         top+(int)row*3,3,3,color);
            }
    }
}

static int finite_limited(float f) {
    return isfinite(f) && f >= -100000.0f && f <= 100000.0f;
}

int hm_raster_render(uint32_t *pixels, uint32_t width, uint32_t height,
                     uint32_t stride, const hm_raster_view *view) {
    const hm_world *w;
    const hm_session *s;
    uint32_t row, col, ev;
    int sx, sy;
    float left, top;
    static const uint32_t sky[6] = {
        UINT32_C(0xff263e65),UINT32_C(0xff325579),
        UINT32_C(0xff42718c),UINT32_C(0xff5d91a0),
        UINT32_C(0xff83a9aa),UINT32_C(0xffa5bda8)
    };
    if (!pixels || !view || !view->world || !view->game ||
        !view->combat || width != HM_RASTER_WIDTH ||
        height != HM_RASTER_HEIGHT ||
        stride < HM_RASTER_WIDTH || stride > 4096u ||
        view->qa_state > 2u) return 0;
    w = view->world;
    s = view->game;
    if (!w->solid || w->columns == 0u || w->rows == 0u ||
        w->columns > 128u || w->rows > 128u ||
        w->tile_size == 0u || w->tile_size > 64u ||
        w->event_count > 32u || (w->event_count && !w->events) ||
        !finite_limited(s->player.x) ||
        !finite_limited(s->player.feet_y) ||
        !finite_limited(s->player.camera_x) ||
        s->player.camera_x < 0.0f ||
        !finite_limited(s->combat.enemy_x) ||
        !finite_limited(view->combat->enemy_feet_y)) return 0;
    /* All arguments, including the borrowed event list, are checked
       BEFORE the first pixel is written. Rejected draws are atomic. */
    for (ev = 0u; ev < w->event_count; ++ev) {
        const hm_event *e = &w->events[ev];
        if (e->kind < HM_PICKUP || e->kind > HM_EXIT ||
            !finite_limited(e->x) || !finite_limited(e->y) ||
            !finite_limited(e->radius) ||
            e->radius < 1.0f || e->radius > 128.0f) return 0;
    }

    left = s->player.camera_x;
    top = s->player.feet_y - 143.0f;
    for (row = 0; row < HM_RASTER_HEIGHT; ++row) {
        const uint32_t band = row / 60u;
        for (col = 0; col < HM_RASTER_WIDTH; ++col)
            pixels[row*stride+col] = sky[band];
    }
    /* Two hand-painted-style, purely mathematical backdrop silhouettes. */
    for (col = 0u; col < HM_RASTER_WIDTH; col += 2u) {
        int ridge = 136+(int)((col/17u + (uint32_t)(left/12.0f+10000.0f))%8u)*6;
        rect(pixels,stride,(int)col,ridge,2,HM_RASTER_HEIGHT-ridge,
             UINT32_C(0xff567b86));
        ridge = 205+(int)((col/29u + (uint32_t)(left/5.0f+10000.0f))%6u)*9;
        rect(pixels,stride,(int)col,ridge,2,HM_RASTER_HEIGHT-ridge,
             UINT32_C(0xff456d75));
    }

    for (row = 0u; row < w->rows; ++row) {
        for (col = 0u; col < w->columns; ++col) {
            const uint8_t cell = w->solid[row*w->columns+col];
            int size=(int)w->tile_size*2;
            if (!cell) continue;
            sx=(int)floorf(((float)(col*w->tile_size)-left)*2.0f);
            sy=(int)floorf(((float)(row*w->tile_size)-top)*2.0f);
            rect(pixels,stride,sx,sy,size,size,UINT32_C(0xff4a413b));
            rect(pixels,stride,sx,sy,size,5,UINT32_C(0xff83a55c));
            rect(pixels,stride,sx+3,sy+8,size-6,size-13,
                 UINT32_C(0xff625449));
        }
    }
    for (ev = 0u; ev < w->event_count; ++ev) {
        const hm_event *e=&w->events[ev];
        sx=(int)floorf((e->x-left)*2.0f);
        sy=(int)floorf((e->y-top)*2.0f);
        if (e->kind == HM_PICKUP) {
            if (!(s->player.picked & (UINT32_C(1)<<ev))) {
                disk(pixels,stride,sx,sy,12,UINT32_C(0xffffd365));
                disk(pixels,stride,sx,sy,5,UINT32_C(0xfffff2b0));
            }
        } else if (e->kind == HM_CHECKPOINT) {
            rect(pixels,stride,sx-6,sy-42,12,48,UINT32_C(0xffded5ac));
            rect(pixels,stride,sx+6,sy-40,25,15,
                 s->player.checkpoint==(int32_t)ev ?
                 UINT32_C(0xff77e4a6):UINT32_C(0xffffcd77));
        } else if (e->kind == HM_HAZARD) {
            rect(pixels,stride,sx-13,sy-15,26,20,UINT32_C(0xffa64048));
            rect(pixels,stride,sx-7,sy-22,14,10,UINT32_C(0xffff846c));
        } else if (e->kind == HM_EXIT) {
            rect(pixels,stride,sx-18,sy-54,36,58,UINT32_C(0xffd2bb7a));
            rect(pixels,stride,sx-10,sy-44,20,48,UINT32_C(0xff253f5e));
        }
    }

    if (s->combat.enemy_hp) {
        sx=(int)floorf((s->combat.enemy_x-left)*2.0f);
        sy=(int)floorf((view->combat->enemy_feet_y-top)*2.0f);
        rect(pixels,stride,sx-10,sy-37,20,37,UINT32_C(0xff814456));
        disk(pixels,stride,sx,sy-45,10,UINT32_C(0xffc68673));
        rect(pixels,stride,sx-12,sy-56,24,7,UINT32_C(0xff493449));
    }
    sx=(int)floorf((s->player.x-left)*2.0f);
    sy=(int)floorf((s->player.feet_y-top)*2.0f);
    /* Custom geometric original test character: blue body, red cape,
       golden head; not an original He-Man sprite or a trademark recreation. */
    rect(pixels,stride,sx-19,sy-45,12,40,UINT32_C(0xffbb4c54));
    rect(pixels,stride,sx-10,sy-47,20,39,UINT32_C(0xff306e9c));
    rect(pixels,stride,sx-10,sy-10,8,11,UINT32_C(0xff31415b));
    rect(pixels,stride,sx+2,sy-10,8,11,UINT32_C(0xff31415b));
    disk(pixels,stride,sx,sy-58,12,UINT32_C(0xffe8b780));
    rect(pixels,stride,sx-13,sy-71,26,10,UINT32_C(0xffd8c264));
    /* Basic sword silhouette: visible while the player is in the scene. */
    rect(pixels,stride,sx+13,sy-46,4,35,UINT32_C(0xffcddae4));
    rect(pixels,stride,sx+8,sy-17,16,4,UINT32_C(0xfff0d486));

    /* Immovable HUD track and unique magenta marker: deliberately tied
       only to world-space player x, never to a moving enemy or camera.
       Emulator screenshots can therefore assert controller-caused motion
       separately from the autonomous synthetic patrol and scenery. */
    rect(pixels,stride,10,44,454,23,UINT32_C(0xff24344a));
    {
        float px = s->player.x * 2.0f;
        int marker_x;
        if (px < 0.0f) px = 0.0f;
        if (px > 420.0f) px = 420.0f;
        marker_x = 20 + (int)floorf(px + 0.5f);
        rect(pixels,stride,marker_x,47,12,16,UINT32_C(0xffff00ff));
    }

    /* Fixed guest-HUD world-y ruler. Camera follows the hero vertically,
       so sprite screen Y alone is not proof that D-pad A caused a jump.
       The cyan marker is driven only by world-space player foot Y, and
       cannot be moved by enemy patrol, backgrounds or moving camera. */
    rect(pixels,stride,468,76,22,257,UINT32_C(0xff283d51));
    {
        float pos = s->player.feet_y - 272.0f;
        int marker_y;
        if (pos < -210.0f) pos = -210.0f;
        if (pos > 20.0f) pos = 20.0f;
        marker_y = 298 + (int)floorf(pos + 0.5f);
        rect(pixels,stride,472,marker_y,14,9,UINT32_C(0xffffff00));
    }

    /* Readable top HUD. Health ticks are clamped to the configured maximum. */
    rect(pixels,stride,0,0,HM_RASTER_WIDTH,38,UINT32_C(0xff1b2c46));
    for (col=0u;col<view->combat->player_initial_hp && col<20u;++col)
        rect(pixels,stride,12+(int)(col*18u),9,14,18,
             col<s->combat.player_hp ?
             UINT32_C(0xffe77965):UINT32_C(0xff493b51));
    for (col=0u;col<view->combat->enemy_initial_hp && col<20u;++col)
        rect(pixels,stride,220+(int)(col*18u),9,14,18,
             col<s->combat.enemy_hp ?
             UINT32_C(0xffe1c86d):UINT32_C(0xff493b51));

    /* Durable player respawn indicator, independent of enemy motion,
       sprite overlap, camera position and animation. Empty track when
       no respawns occurred; bright green once the *native* counter rises.
       The test reads RGB bytes at (522,62) from real guest PNG frames. */
    rect(pixels,stride,512,48,26,26,UINT32_C(0xff283d51));
    if (s->player.respawns > 0u)
        rect(pixels,stride,516,52,18,18,UINT32_C(0xff42d58a));

    rect(pixels,stride,480,5,152,29,
         view->qa_state==1u ? UINT32_C(0xff347f5d) :
         view->qa_state==2u ? UINT32_C(0xffaf4e54) :
                              UINT32_C(0xff354967));
    hex_score(pixels,stride,view->qa_fingerprint,495,11,
              UINT32_C(0xfff1e6bf));
    return 1;
}
