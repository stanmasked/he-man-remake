/* Synthetic-only Switch guest for the Stage172 sprite-clock oracle.
   Three flat color swatches stand in for frames. No game art or resources. */
#include <switch.h>
#include <stdint.h>
#include <string.h>
#include "heman_sprite_clock.h"
#include "heman_app_tick_scheduler.h"

#define SCREEN_W 640u
#define SCREEN_H 360u

static void rect(uint32_t *pixels, uint32_t stride, int x0, int y0,
                 int x1, int y1, uint32_t color) {
    int x, y;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > (int)SCREEN_W) x1 = (int)SCREEN_W;
    if (y1 > (int)SCREEN_H) y1 = (int)SCREEN_H;
    for (y = y0; y < y1; ++y)
        for (x = x0; x < x1; ++x)
            pixels[(uint32_t)y * stride + (uint32_t)x] = color;
}

int main(int argc, char **argv) {
    static const int32_t boundaries[] = {0, 240, 480, 720};
    static const int32_t loop_setting = 1;
    static const float rates[] = {0.5f, 1.0f, 2.0f};
    static const uint32_t frame_colors[] = {
        UINT32_C(0xffd85b48), UINT32_C(0xff47b9d1), UINT32_C(0xff7ac45b)
    };
    Framebuffer fb;
    PadState pad;
    Result rc;
    hm_sprite_clock_state state = {0, 0, loop_setting};
    static const int32_t callback_ms_pattern[] = {16, 17, 17};
    int32_t wall_accumulator_ms = 0;
    uint32_t callback_index = 0u;
    unsigned rate_index = 1u;
    int active = 1;
    int clock_error = 0;
    (void)argc;
    (void)argv;
    memset(&fb, 0, sizeof fb);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);
    rc = framebufferCreate(&fb, nwindowGetDefault(), SCREEN_W, SCREEN_H,
                           PIXEL_FORMAT_RGBA_8888, 2);
    if (R_FAILED(rc)) return 2;
    rc = framebufferMakeLinear(&fb);
    if (R_FAILED(rc)) {
        framebufferClose(&fb);
        return 3;
    }

    while (appletMainLoop()) {
        uint32_t row, col, stride = 0u;
        uint32_t *pixels, scheduled_updates = 0u, update_index;
        int32_t synthetic_wall_delta_ms;
        uint64_t down;
        int finished = 0;
        padUpdate(&pad);
        down = padGetButtonsDown(&pad);
        if (down & HidNpadButton_Plus) break;
        if (down & HidNpadButton_A) active = !active;
        if (down & HidNpadButton_B) {
            state.frame_index = 0;
            state.elapsed_ticks = 0;
            state.remaining_replays = loop_setting;
            wall_accumulator_ms = 0;
            clock_error = 0;
        }
        if (down & HidNpadButton_Y) rate_index = (rate_index + 1u) % 3u;
        synthetic_wall_delta_ms =
            callback_ms_pattern[callback_index % 3u];
        ++callback_index;
        if (!clock_error &&
            hm_app_tick_scheduler_advance(&wall_accumulator_ms,
                                          synthetic_wall_delta_ms,
                                          &scheduled_updates) != HM_APP_TICK_OK) {
            clock_error = 1;
        }
        for (update_index = 0u;
             update_index < scheduled_updates && !clock_error;
             ++update_index) {
            if (hm_sprite_clock_step(boundaries, 3u, loop_setting, &state,
                                     0.04f, rates[rate_index],
                                     active, 128u) != HM_SPRITE_CLOCK_OK) {
                clock_error = 1;
            }
        }
        (void)hm_sprite_clock_is_finished(boundaries, 3u, loop_setting,
                                          &state, &finished);
        pixels = (uint32_t *)framebufferBegin(&fb, &stride);
        if (!pixels || stride % sizeof(uint32_t) != 0u) break;
        stride /= sizeof(uint32_t);
        if (stride < SCREEN_W) {
            framebufferEnd(&fb);
            break;
        }

        for (row = 0u; row < SCREEN_H; ++row)
            for (col = 0u; col < SCREEN_W; ++col)
                pixels[row * stride + col] = UINT32_C(0xff182337);

        /* Fictional timeline, frame selection, rate and active indicators. */
        rect(pixels, stride, 40, 32, 600, 40, UINT32_C(0xff39465d));
        rect(pixels, stride, 40, 32, 40 + (active ? 280 : 90), 40,
             active ? UINT32_C(0xff59c98a) : UINT32_C(0xffe7b85c));
        rect(pixels, stride, 40, 54, 600, 66, UINT32_C(0xff39465d));
        rect(pixels, stride, 40, 54, 40 + (int)(rate_index + 1u) * 80, 66,
             UINT32_C(0xffaa8be8));
        rect(pixels, stride, 40, 76, 600, 84, UINT32_C(0xff39465d));
        rect(pixels, stride, 40, 76, 40 + (int)scheduled_updates * 80, 84,
             UINT32_C(0xffffd166));
        rect(pixels, stride, 120, 100, 520, 276,
             clock_error ? UINT32_C(0xffe84a5f) :
             (state.frame_index >= 0 && state.frame_index < 3 ?
              frame_colors[state.frame_index] : UINT32_C(0xff777777)));
        rect(pixels, stride, 130, 286, 510, 300, UINT32_C(0xff39465d));
        {
            int width = (int)((state.elapsed_ticks > 720 ? 720 :
                               state.elapsed_ticks) * 380 / 720);
            if (width < 0) width = 0;
            rect(pixels, stride, 130, 286, 130 + width, 300,
                 UINT32_C(0xffffd166));
        }
        /* Three numbered abstract frame markers; the selected one is white. */
        for (col = 0u; col < 3u; ++col) {
            const int x = 230 + (int)col * 70;
            rect(pixels, stride, x, 320, x + 44, 342,
                 !clock_error && state.frame_index == (int32_t)col ?
                 UINT32_C(0xffffffff) : UINT32_C(0xff59677c));
        }
        /* Finished-state strip only comes from the native strict-end predicate. */
        if (finished)
            rect(pixels, stride, 40, 348, 600, 356, UINT32_C(0xfff0f0f0));
        if (clock_error)
            rect(pixels, stride, 40, 348, 600, 356, UINT32_C(0xffe84a5f));

        framebufferEnd(&fb);
        svcSleepThread(16666667LL);
    }
    framebufferClose(&fb);
    return clock_error ? 5 : 0;
}
