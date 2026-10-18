/* Asset-free Nintendo Switch C99 *probe*, not a remade He-Man game.
   Uses a 40x20 tile-map console view, not original game sprites. */
#include <switch.h>
#include <stdio.h>
#include <string.h>
#include "heman_core.h"
#include "heman_combat.h"
#include "heman_session.h"
#include "probe_view.h"
#include "probe_selfcheck.h"
#include "session_selftest.h"

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

static hm_combat_config make_combat(void) {
    hm_combat_config c;
    memset(&c, 0, sizeof(c));
    c.patrol_left = 220.0f; c.patrol_right = 355.0f;
    c.enemy_start_x = 290.0f; c.enemy_feet_y = 272.0f;
    c.enemy_speed = 38.0f; c.sword_reach = 30.0f;
    c.contact_range = 9.0f; c.enemy_initial_hp = 2u;
    c.player_initial_hp = 3u; c.sword_cooldown_frames = 15u;
    c.hurt_cooldown_frames = 45u;
    return c;
}

/* Retain diagnostic codes on screen until Plus/app termination. */
static void show_failure_screen(PadState *pad, const char *stage,
                                int session_error, int boot_error) {
    printf("\x1b[2J\x1b[H");
    printf("He-Man independent Switch core probe: FAILED\n\n");
    printf("Stage: %s\n", stage);
    printf("session result %d | startup self-check %d\n",
           session_error, boot_error);
    printf("Press + to quit. Record these codes for diagnosis.\n");
    consoleUpdate(NULL);
    while (appletMainLoop()) {
        padUpdate(pad);
        if (padGetButtonsDown(pad) & HidNpadButton_Plus) break;
        svcSleepThread(16000000LL);
    }
}

int main(void) {
    hm_world world = make_world();
    hm_combat_config combat_cfg = make_combat();
    hm_session game;
    hm_session_result result = hm_session_init(&world, &combat_cfg, &game);
    hm_probe_check_result boot_check = hm_probe_boot_selfcheck();
    hm_session_selftest_code session_check = hm_session_selftest();
    PadState pad;
    char view[HM_PROBE_BYTES];
    uint32_t row;
    consoleInit(NULL);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);
    if (result != HM_SESSION_OK || boot_check != HM_PROBE_CHECK_OK ||
        session_check != HM_SESSION_SELFTEST_OK) {
        show_failure_screen(&pad, "startup", (int)result,
                            boot_check != HM_PROBE_CHECK_OK ? (int)boot_check :
                            100 + (int)session_check);
        consoleExit(NULL);
        return 1;
    }
    while (appletMainLoop()) {
        hm_input movement = {0.0f, 0u, 0u};
        uint64_t down, held;
        padUpdate(&pad);
        down = padGetButtonsDown(&pad);
        held = padGetButtons(&pad);
        if (down & HidNpadButton_Plus) break;
        if (held & HidNpadButton_Left) movement.axis -= 1.0f;
        if (held & HidNpadButton_Right) movement.axis += 1.0f;
        movement.jump = (uint8_t)((down & HidNpadButton_A) != 0);
        movement.reset = (uint8_t)((down & HidNpadButton_B) != 0);
        result = hm_session_step(&world, &combat_cfg, &game, movement,
                  (uint8_t)((down & HidNpadButton_X) != 0), 1.0f / 60.0f);
        if (result != HM_SESSION_OK) break;
        if (game.player.frame % 6u == 0u) {
            if (!hm_probe_render(&world, &game.player, view, sizeof(view))) {
                result = HM_SESSION_INVALID;
                break;
            }
            if (game.combat.enemy_hp > 0u &&
                !hm_probe_overlay_marker(&world, &game.player, view,
                    sizeof(view), game.combat.enemy_x,
                    combat_cfg.enemy_feet_y - 10.0f, 'E')) {
                result = HM_SESSION_INVALID;
                break;
            }
            printf("\x1b[2J\x1b[H");
            printf("He-Man independent C99 Switch core probe\n");
            printf("Startup: PASS (physics 180f + combined session)\n");
            printf("Left/Right: move | A: jump | X: attack | B: reset | +: quit\n");
            printf("@ player  # platform  * pickup  C checkpoint\n");
            printf("! hazard  > exit  E: enemy (synthetic only)\n");
            for (row = 0; row < HM_PROBE_ROWS; ++row)
                printf("|%s|\n", &view[row * HM_PROBE_STRIDE]);
            printf("frame %lu | x %.1f feet %.1f vy %.1f\n",
                   (unsigned long)game.player.frame, game.player.x,
                   game.player.feet_y, game.player.vy);
            printf("ground %u wall %u ceiling %u | respawns %lu\n",
                   game.player.grounded, game.player.wall_hit,
                   game.player.ceiling_hit,
                   (unsigned long)game.player.respawns);
            printf("HP %u | enemy HP %u | sword hits %lu | taken %lu\n",
                   game.combat.player_hp, game.combat.enemy_hp,
                   (unsigned long)game.combat.sword_hits,
                   (unsigned long)game.combat.player_hits);
            printf("pickup %s checkpoint %ld hazards %lu exit %s\n",
                   game.player.picked ? "yes" : "no",
                   (long)game.player.checkpoint,
                   (unsigned long)game.player.hazards,
                   game.player.completed ? "yes" : "no");
            consoleUpdate(NULL);
        }
        /* Nominal frame step; not hardware-accurate frame pacing. */
        svcSleepThread(16000000LL);
    }
    if (result != HM_SESSION_OK)
        show_failure_screen(&pad, "gameplay/viewport", (int)result,
                            (int)boot_check);
    consoleExit(NULL);
    return result == HM_SESSION_OK ? 0 : 2;
}
