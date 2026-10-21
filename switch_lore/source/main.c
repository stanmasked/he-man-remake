/* Original-asset-free opt-in Level 1-1 mechanics Switch laboratory.
 * All geometry/pixels are FICTIONAL. NOT the original iOS game level. */
#include <switch.h>
#include <stdint.h>
#include <string.h>
#include "heman_level11_lab.h"
#include "heman_level11_durable_save.h"

#define WIDTH 640u
#define HEIGHT 360u
#define ORIGIN_X 64
#define ORIGIN_Y 74

static uint8_t tiles[HM_LORE_LAB_CELLS];
static hm_world world;
static hm_level11_native_session session;
static hm_level11_lab_save saved;
static int durable_status;
#define DURABLE_SAVE_PREFIX "sdmc:/switch/heman_level11_lore_lab"

/* Guard the complete destination including pixels outside the framebuffer.
 * All coordinates are pixel coordinates, not original-game asset positions. */
static void rectangle(uint32_t *pixels, uint32_t stride, int x, int y,
                      int width, int height, uint32_t color) {
    int xx, yy;
    if (!pixels || stride < WIDTH || width <= 0 || height <= 0)
        return;
    for (yy = y < 0 ? 0 : y; yy < y + height && yy < (int)HEIGHT; ++yy) {
        for (xx = x < 0 ? 0 : x; xx < x + width && xx < (int)WIDTH; ++xx)
            pixels[(uint32_t)yy * stride + (uint32_t)xx] = color;
    }
}
static void scene(uint32_t *pixels, uint32_t stride) {
    uint32_t x, y, k;
    const uint32_t bg = UINT32_C(0xff121c27);
    const uint32_t block = UINT32_C(0xff506078);
    const uint32_t hero = UINT32_C(0xffffdc90);
    const uint32_t cyan = UINT32_C(0xff69e8db);
    const uint32_t violet = UINT32_C(0xffe079cd);
    const uint32_t green = UINT32_C(0xff55df7c);
    const uint32_t grey = UINT32_C(0xff404858);
    rectangle(pixels, stride, 0, 0, WIDTH, HEIGHT, bg);
    rectangle(pixels, stride, 0, 290, WIDTH, 70, UINT32_C(0xff1b2532));
    for (y = 0; y < world.rows; ++y) {
        for (x = 0; x < world.columns; ++x) {
            if (tiles[y * world.columns + x])
                rectangle(pixels, stride, ORIGIN_X + (int)x * 16,
                          ORIGIN_Y + (int)y * 16, 16, 16, block);
        }
    }
    for (k = 0; k < world.event_count; ++k) {
        const hm_event *e = &world.events[k];
        uint32_t color = k == 0 ? UINT32_C(0xffefb54d) :
                         k == 1 ? violet : cyan;
        if (k == 0 && session.lore.left_gate_broken)
            color = green;
        if (k == 1 && (session.lore.collected_mask & 1u))
            color = grey;
        if (k == 2 && (session.lore.collected_mask & 2u))
            color = grey;
        rectangle(pixels, stride, ORIGIN_X + (int)e->x - 5,
                  ORIGIN_Y + (int)e->y - 5, 11, 11, color);
    }
    rectangle(pixels, stride, ORIGIN_X + (int)session.player.x - 5,
              ORIGIN_Y + (int)session.player.feet_y - 20,
              10, 20, hero);
    /* Seven large visual-only status bars in a fixed order.
     * Labels are in README, no commercial art or fonts included. */
    rectangle(pixels, stride, 24, 22, 42, 15,
              session.lore.wall_crusher_unlocked ? green : grey);
    rectangle(pixels, stride, 78, 22, 42, 15,
              session.lore.left_gate_broken ? green : grey);
    rectangle(pixels, stride, 132, 22, 42, 15,
              session.lore.collected_mask & 1u ? violet : grey);
    rectangle(pixels, stride, 186, 22, 42, 15,
              session.lore.collected_mask & 2u ? cyan : grey);
    rectangle(pixels, stride, 240, 22, 42, 15,
              saved.valid ? UINT32_C(0xff688cff) : grey);
    rectangle(pixels, stride, 310, 22, 24, 15,
              session.attack_previous_down ? UINT32_C(0xffe88b58) : grey);
    rectangle(pixels, stride, 350, 22, 6 + 14 * session.lore.collected_count,
              15, green);
    /* Separate persistent-save HUD, never conflated with L/R RAM save.
     * ZL disk save: green, ZR disk load: cyan, error: red, idle: grey. */
    rectangle(pixels, stride, 425, 22, 35, 15,
              durable_status==1 ? green :
              durable_status==2 ? cyan :
              durable_status<0 ? UINT32_C(0xff4e4eff) : grey);
}
static uint32_t controls(uint64_t buttons) {
    uint32_t value = 0u;
    if (buttons & HidNpadButton_Left) value |= HM_LAB_LEFT;
    if (buttons & HidNpadButton_Right) value |= HM_LAB_RIGHT;
    if (buttons & HidNpadButton_A) value |= HM_LAB_JUMP;
    if (buttons & HidNpadButton_X) value |= HM_LAB_ATTACK;
    if (buttons & HidNpadButton_Y) value |= HM_LAB_WALL_UPGRADE;
    if (buttons & HidNpadButton_B) value |= HM_LAB_RESET;
    if (buttons & HidNpadButton_L) value |= HM_LAB_SAVE;
    if (buttons & HidNpadButton_R) value |= HM_LAB_LOAD;
    return value;
}
int main(int argc, char **argv) {
    Framebuffer fb;
    PadState pad;
    Result result;
    uint32_t stride = 0u;
    int code = 0;
    (void)argc; (void)argv;
    memset(&saved, 0, sizeof(saved));
    if (hm_level11_lab_init(&world, tiles, sizeof(tiles), &session)
            != HM_LORE_APPLIED) return 2;
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);
    memset(&fb, 0, sizeof(fb));
    result = framebufferCreate(&fb, nwindowGetDefault(), WIDTH, HEIGHT,
                               PIXEL_FORMAT_RGBA_8888, 2);
    if (R_FAILED(result)) return 3;
    result = framebufferMakeLinear(&fb);
    if (R_FAILED(result)) {
        framebufferClose(&fb);
        return 4;
    }
    while (appletMainLoop()) {
        uint64_t held, down;
        uint32_t *pixels;
        hm_lore_result tick;
        padUpdate(&pad);
        held = padGetButtons(&pad);
        down = padGetButtonsDown(&pad);
        if (down & HidNpadButton_Plus) break;
        if (down & HidNpadButton_ZL) {
            durable_status=hm_level11_durable_store(DURABLE_SAVE_PREFIX,
                                                    &session)==HM_DURABLE_OK
                           ?1:-1;
            tick=HM_LORE_BLOCKED;
        } else if (down & HidNpadButton_ZR) {
            durable_status=hm_level11_durable_load(DURABLE_SAVE_PREFIX,
                                                   &session)==HM_DURABLE_OK
                           ?2:-1;
            tick=HM_LORE_BLOCKED;
        } else {
            tick = hm_level11_lab_tick(&session, &saved,
                                      controls(held), controls(down));
        }
        if (tick == HM_LORE_INVALID) { code = 5; break; }
        pixels = (uint32_t*)framebufferBegin(&fb, &stride);
        if (!pixels || (stride % sizeof(uint32_t)) != 0u ||
            stride / sizeof(uint32_t) < WIDTH) {
            if (pixels) framebufferEnd(&fb);
            code = 6;
            break;
        }
        scene(pixels, stride / sizeof(uint32_t));
        framebufferEnd(&fb);
        svcSleepThread(16666667LL);
    }
    framebufferClose(&fb);
    return code;
}
