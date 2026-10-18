/* Asset-free Nintendo Switch C99 *probe*, not a remade He-Man game.
   Uses a 40x20 tile-map console view, not original game sprites. */
#include <switch.h>
#include <stdio.h>
#include <string.h>
#include "heman_core.h"
#include "probe_view.h"
#include "probe_selfcheck.h"

#define W 48u
#define H 24u
#define T 16u
static uint8_t level[W * H];
static const hm_event markers[] = {
    { HM_PICKUP,     170.0f, 251.0f,  8.0f },
    { HM_CHECKPOINT, 340.0f, 257.0f,  8.0f },
    { HM_HAZARD,     585.0f, 257.0f,  8.0f },
    { HM_EXIT,       728.0f, 257.0f,  8.0f }
};

static hm_world make_world(void) {
    hm_world w;
    unsigned x;
    memset(&w, 0, sizeof(w));
    memset(level, 0, sizeof(level));
    for (x = 0; x < W; ++x) level[17u * W + x] = 1;
    for (x = 15; x < 18; ++x) level[15u * W + x] = 1;
    w.solid = level;
    w.columns = W; w.rows = H; w.tile_size = T;
    w.spawn_x = 50; w.spawn_feet_y = 17 * T;
    w.actor_half_width = 5; w.actor_height = 22;
    w.speed = 120; w.gravity = 1200; w.jump_speed = 420;
    w.terminal_speed = 1400;
    w.viewport_width = 320; w.viewport_height = 240; w.death_margin = 96;
    w.events = markers; w.event_count = sizeof(markers) / sizeof(markers[0]);
    return w;
}

int main(void) {
    hm_world world = make_world();
    hm_state state;
    PadState pad;
    hm_result result = hm_init(&world, &state);
    hm_probe_check_result boot_check = hm_probe_boot_selfcheck();
    char view[HM_PROBE_BYTES];
    uint32_t row;
    consoleInit(NULL);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);
    if (result != HM_OK || boot_check != HM_PROBE_CHECK_OK) {
        printf("Core setup error: %d; boot self-check: %d\n",
               (int)result, (int)boot_check);
        consoleUpdate(NULL);
        consoleExit(NULL);
        return 1;
    }
    while (appletMainLoop()) {
        hm_input input = {0.0f, 0, 0};
        uint64_t down, held;
        padUpdate(&pad);
        down = padGetButtonsDown(&pad);
        held = padGetButtons(&pad);
        if (down & HidNpadButton_Plus) break;
        if (held & HidNpadButton_Left) input.axis -= 1.0f;
        if (held & HidNpadButton_Right) input.axis += 1.0f;
        input.jump = (uint8_t)((down & HidNpadButton_A) != 0);
        input.reset = (uint8_t)((down & HidNpadButton_B) != 0);
        result = hm_step(&world, &state, input, 1.0f / 60.0f);
        if (result != HM_OK) break;
        if (state.frame % 6u == 0u) {
            if (!hm_probe_render(&world, &state, view, sizeof(view))) {
                result = HM_INVALID;
                break;
            }
            printf("\x1b[2J\x1b[H");
            printf("He-Man independent C99 Switch core probe\n");
            printf("Synthetic boot self-check: PASS (180 scripted frames)\n");
            printf("Left/Right: move | A: jump | B: reset | +: quit\n");
            printf("@ player  # platform  * pickup  C checkpoint\n");
            printf("! hazard  > exit  (all level content synthetic)\n");
            for (row = 0; row < HM_PROBE_ROWS; ++row)
                printf("|%s|\n", &view[row * HM_PROBE_STRIDE]);
            printf("frame %lu | x %.1f feet %.1f vy %.1f\n",
                   (unsigned long)state.frame, state.x, state.feet_y, state.vy);
            printf("ground %u wall %u ceiling %u | respawns %lu\n",
                   state.grounded, state.wall_hit, state.ceiling_hit,
                   (unsigned long)state.respawns);
            printf("pickup %s checkpoint %ld hazards %lu exit %s\n",
                   state.picked ? "yes" : "no", (long)state.checkpoint,
                   (unsigned long)state.hazards,
                   state.completed ? "yes" : "no");
            consoleUpdate(NULL);
        }
        /* Approximate fixed-step pacing; no runtime timing proof yet. */
        svcSleepThread(16000000LL);
    }
    if (result != HM_OK) {
        printf("Core runtime error: %d\n", (int)result);
        consoleUpdate(NULL);
    }
    consoleExit(NULL);
    return result == HM_OK ? 0 : 2;
}
