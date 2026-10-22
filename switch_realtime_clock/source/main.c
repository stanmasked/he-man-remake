/* Stage183: asset-free real-time app-clock probe for Nintendo Switch.
   This is not a playable He-Man build and contains no original game assets. */
#include <switch.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "heman_app_tick_clock.h"
#include "heman_app_tick_scheduler.h"
#include "heman_sprite_clock.h"

static const int32_t k_frame_boundaries[] = {0, 240, 480, 720};
static const uint32_t k_frame_count = 3u;
static const int32_t k_loop_setting = -1;
static const uint32_t k_max_sprite_steps = 128u;
static const int64_t k_loop_sleep_ns = 16666667LL;
static uint64_t g_origin_ticks;

typedef struct {
    uint64_t pause_500ms_observed_ns;
    uint64_t pause_200ms_observed_ns;
    int32_t first_resume_ms;
    int32_t second_resume_ms;
    int32_t normal_callback_ms;
    uint32_t total_updates;
    int32_t final_accumulator_ms;
    int32_t final_player_ticks;
} selfcheck_report;

static uint64_t monotonic_ns(void) {
    /* Use a launch-relative counter so armTicksToNs never needs to convert an
       unbounded absolute uptime value. The source is libnx's system counter. */
    return armTicksToNs(armGetSystemTick() - g_origin_ticks);
}

static uint64_t elapsed_counter_ns(uint64_t before_ticks,
                                   uint64_t after_ticks) {
    return armTicksToNs(after_ticks - before_ticks);
}

static int apply_updates(hm_sprite_clock_state *player, uint32_t updates,
                         uint32_t *total_updates, int playback_active) {
    uint32_t i;
    for (i = 0u; i < updates; ++i) {
        if (hm_sprite_clock_step(k_frame_boundaries, k_frame_count,
                                 k_loop_setting, player, 0.04f, 1.0f,
                                 playback_active, k_max_sprite_steps) !=
            HM_SPRITE_CLOCK_OK) {
            return 0;
        }
        ++(*total_updates);
    }
    return 1;
}

/* One handler dispatch. The identical-timestamp second sample proves the
   bridge committed the resumed baseline, rather than leaving a stale pause
   timestamp that would be replayed by the next callback. */
static int dispatch_clock(hm_app_tick_clock_state *clock,
                          int32_t *accumulator_ms,
                          hm_sprite_clock_state *player,
                          uint32_t *total_updates,
                          int32_t *elapsed_ms_out,
                          uint32_t *updates_out) {
    uint64_t sample_ns = monotonic_ns();
    int32_t elapsed_ms = -1, zero_ms = -1;
    uint32_t updates = 0u;

    if (hm_app_tick_clock_sample(clock, sample_ns, &elapsed_ms) !=
        HM_APP_TICK_CLOCK_OK) return 0;
    if (hm_app_tick_scheduler_advance(accumulator_ms, elapsed_ms, &updates) !=
        HM_APP_TICK_OK) return 0;
    if (!apply_updates(player, updates, total_updates, 1)) return 0;
    if (hm_app_tick_clock_sample(clock, sample_ns, &zero_ms) !=
            HM_APP_TICK_CLOCK_OK || zero_ms != 0) return 0;

    *elapsed_ms_out = elapsed_ms;
    *updates_out = updates;
    return 1;
}

/* This startup check deliberately omits clock sampling during two real
   sleeps. It verifies that the first resumed dispatch sees a capped 66-ms
   interval, consumes four fixed updates, and commits a fresh time baseline. */
static int run_platform_selfcheck(selfcheck_report *report) {
    hm_app_tick_clock_state clock;
    hm_sprite_clock_state player = {0, 0, k_loop_setting};
    int32_t accumulator_ms = 0, elapsed_ms = -1;
    uint32_t updates = 0u, total_updates = 0u;
    uint64_t before_ticks, after_ticks, initial_ns;

    memset(report, 0, sizeof(*report));
    if (armGetSystemTickFreq() == 0u) return 1;

    hm_app_tick_clock_init(&clock);
    initial_ns = monotonic_ns();
    if (hm_app_tick_clock_sample(&clock, initial_ns, &elapsed_ms) !=
            HM_APP_TICK_CLOCK_OK || elapsed_ms != 0) return 2;

    before_ticks = armGetSystemTick();
    svcSleepThread(500000000LL);
    after_ticks = armGetSystemTick();
    report->pause_500ms_observed_ns =
        elapsed_counter_ns(before_ticks, after_ticks);
    if (report->pause_500ms_observed_ns < UINT64_C(66000000)) return 3;
    if (!dispatch_clock(&clock, &accumulator_ms, &player, &total_updates,
                        &elapsed_ms, &updates)) return 4;
    report->first_resume_ms = elapsed_ms;
    if (elapsed_ms != HM_APP_TICK_MAX_ACCUMULATOR_MS || updates != 4u ||
        accumulator_ms != 2 || total_updates != 4u ||
        player.elapsed_ticks != 160) return 5;

    before_ticks = armGetSystemTick();
    svcSleepThread(200000000LL);
    after_ticks = armGetSystemTick();
    report->pause_200ms_observed_ns =
        elapsed_counter_ns(before_ticks, after_ticks);
    if (report->pause_200ms_observed_ns < UINT64_C(66000000)) return 6;
    if (!dispatch_clock(&clock, &accumulator_ms, &player, &total_updates,
                        &elapsed_ms, &updates)) return 7;
    report->second_resume_ms = elapsed_ms;
    if (elapsed_ms != HM_APP_TICK_MAX_ACCUMULATOR_MS || updates != 4u ||
        accumulator_ms != 2 || total_updates != 8u ||
        player.elapsed_ticks != 320) return 8;

    before_ticks = armGetSystemTick();
    svcSleepThread(16000000LL);
    after_ticks = armGetSystemTick();
    if (elapsed_counter_ns(before_ticks, after_ticks) <
        UINT64_C(16000000)) return 9;
    if (!dispatch_clock(&clock, &accumulator_ms, &player, &total_updates,
                        &elapsed_ms, &updates)) return 10;
    report->normal_callback_ms = elapsed_ms;
    if (elapsed_ms < 16 || elapsed_ms > HM_APP_TICK_MAX_ACCUMULATOR_MS ||
        updates == 0u || updates > HM_APP_TICK_MAX_STEPS_PER_CALLBACK ||
        accumulator_ms < 0 || accumulator_ms >= HM_APP_TICK_QUANTUM_MS ||
        player.elapsed_ticks != (int32_t)total_updates * 40) return 11;

    report->total_updates = total_updates;
    report->final_accumulator_ms = accumulator_ms;
    report->final_player_ticks = player.elapsed_ticks;
    return 0;
}

static void print_failure(PadState *pad, int error_code) {
    printf("\x1b[2J\x1b[H");
    printf("He-Man Stage183 real-time clock probe: FAIL\n\n");
    printf("Startup self-check code: %d\n", error_code);
    printf("System counter frequency: %llu Hz\n",
           (unsigned long long)armGetSystemTickFreq());
    printf("Press + to exit.\n");
    consoleUpdate(NULL);
    while (appletMainLoop()) {
        padUpdate(pad);
        if (padGetButtonsDown(pad) & HidNpadButton_Plus) break;
        svcSleepThread(k_loop_sleep_ns);
    }
}

int main(void) {
    hm_app_tick_clock_state clock;
    hm_sprite_clock_state player = {0, 0, k_loop_setting};
    selfcheck_report report;
    PadState pad;
    int32_t accumulator_ms = 0, last_elapsed_ms = 0;
    uint32_t last_updates = 0u, total_updates = 0u, display_counter = 0u;
    int dispatch_enabled = 1, playback_active = 1, clock_error = 0;
    int selfcheck_code;

    g_origin_ticks = armGetSystemTick();
    consoleInit(NULL);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);

    selfcheck_code = run_platform_selfcheck(&report);
    if (selfcheck_code != 0) {
        print_failure(&pad, selfcheck_code);
        consoleExit(NULL);
        return 10 + selfcheck_code;
    }

    hm_app_tick_clock_init(&clock);
    if (hm_app_tick_clock_sample(&clock, monotonic_ns(), &last_elapsed_ms) !=
        HM_APP_TICK_CLOCK_OK) {
        print_failure(&pad, 12);
        consoleExit(NULL);
        return 12;
    }

    while (appletMainLoop()) {
        uint64_t down;
        padUpdate(&pad);
        down = padGetButtonsDown(&pad);
        if (down & HidNpadButton_Plus) break;
        if (down & HidNpadButton_A) dispatch_enabled = !dispatch_enabled;
        if (down & HidNpadButton_X) playback_active = !playback_active;
        if (down & HidNpadButton_B) {
            hm_app_tick_clock_init(&clock);
            player.frame_index = 0;
            player.elapsed_ticks = 0;
            player.remaining_replays = k_loop_setting;
            accumulator_ms = 0;
            last_elapsed_ms = 0;
            last_updates = 0u;
            total_updates = 0u;
            clock_error = hm_app_tick_clock_sample(
                &clock, monotonic_ns(), &last_elapsed_ms) != HM_APP_TICK_CLOCK_OK;
        }

        /* When the app-level gate is off, intentionally do not sample the
           clock or advance the accumulator. The resumed callback sees the
           elapsed interval since the last dispatched callback. */
        if (dispatch_enabled && !clock_error) {
            uint64_t sample_ns = monotonic_ns();
            uint32_t updates = 0u;
            int32_t elapsed_ms = 0;
            if (hm_app_tick_clock_sample(&clock, sample_ns, &elapsed_ms) !=
                    HM_APP_TICK_CLOCK_OK ||
                hm_app_tick_scheduler_advance(&accumulator_ms, elapsed_ms,
                                              &updates) != HM_APP_TICK_OK ||
                !apply_updates(&player, updates, &total_updates,
                               playback_active)) {
                clock_error = 1;
            } else {
                last_elapsed_ms = elapsed_ms;
                last_updates = updates;
            }
        }

        if (clock_error) {
            print_failure(&pad, 13);
            break;
        }

        if ((display_counter++ & 3u) == 0u) {
            printf("\x1b[2J\x1b[H");
            printf("He-Man Stage183: real-time app-clock probe\n");
            printf("Synthetic only; not original game code/assets\n\n");
            printf("Startup real-counter pause/resume self-check: PASS\n");
            printf("Counter frequency: %llu Hz\n",
                   (unsigned long long)armGetSystemTickFreq());
            printf("Observed sleeps: %llu ms and %llu ms\n",
                   (unsigned long long)(report.pause_500ms_observed_ns /
                                        UINT64_C(1000000)),
                   (unsigned long long)(report.pause_200ms_observed_ns /
                                        UINT64_C(1000000)));
            printf("A: app dispatch gate %s (OFF skips clock sampling)\n",
                   dispatch_enabled ? "ON" : "OFF");
            printf("X: player clock %s (scheduler still runs)\n",
                   playback_active ? "ACTIVE" : "PAUSED");
            printf("Last wall delta: %ld ms | updates: %lu | remainder: %ld ms\n",
                   (long)last_elapsed_ms, (unsigned long)last_updates,
                   (long)accumulator_ms);
            printf("Total updates: %lu | player ticks: %ld | frame: %ld\n",
                   (unsigned long)total_updates, (long)player.elapsed_ticks,
                   (long)player.frame_index);
            printf("Self-check: resumes capped at %ld ms; final %lu updates\n",
                   (long)HM_APP_TICK_MAX_ACCUMULATOR_MS,
                   (unsigned long)report.total_updates);
            printf("B reset | + exit\n");
            consoleUpdate(NULL);
        }
        svcSleepThread(k_loop_sleep_ns);
    }

    consoleExit(NULL);
    return 0;
}
