#include "runtime_replay.h"
#include "heman_session.h"

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define R_COLS 32u
#define R_ROWS 20u
#define R_FRAMES 180u
#define R_FNV_OFFSET UINT32_C(2166136261)
#define R_FNV_PRIME UINT32_C(16777619)

static uint32_t mix_u32(uint32_t hash, uint32_t value) {
    /* Byte-order-independent FNV-1a feed; never hash structure padding. */
    unsigned i;
    for (i = 0; i < 4u; ++i) {
        hash = (hash ^ (value & 255u)) * R_FNV_PRIME;
        value >>= 8;
    }
    return hash;
}

static uint32_t quantize_position(float x) {
    /* 1/8 pixel resolution for readable comparison across builds. */
    if (!isfinite(x) || x < -100000.0f || x > 100000.0f)
        return UINT32_MAX;
    return (uint32_t)((int32_t)floorf(x * 8.0f + 0.5f));
}

hm_replay_status hm_replay_run(hm_replay_report *out) {
    uint8_t tiles[R_COLS * R_ROWS];
    const hm_event events[] = {
        { HM_PICKUP, 80.0f, 210.0f, 8.0f },
        { HM_CHECKPOINT, 128.0f, 210.0f, 8.0f }
    };
    hm_world world;
    hm_combat_config config;
    hm_session game;
    hm_replay_report next;
    uint32_t frame, col, h = R_FNV_OFFSET;

    if (!out) return HM_REPLAY_BAD_ARGUMENT;
    memset(tiles, 0, sizeof(tiles));
    memset(&world, 0, sizeof(world));
    memset(&config, 0, sizeof(config));
    memset(&next, 0, sizeof(next));
    for (col = 0; col < R_COLS; ++col)
        tiles[14u * R_COLS + col] = 1u;
    world.solid = tiles;
    world.columns = R_COLS; world.rows = R_ROWS; world.tile_size = 16u;
    world.spawn_x = 32.0f; world.spawn_feet_y = 224.0f;
    world.actor_half_width = 5.0f; world.actor_height = 22.0f;
    world.speed = 120.0f; world.gravity = 1200.0f;
    world.jump_speed = 420.0f; world.terminal_speed = 1400.0f;
    world.viewport_width = 320.0f; world.viewport_height = 240.0f;
    world.death_margin = 96.0f;
    world.events = events; world.event_count = 2u;
    config.patrol_left = 180.0f; config.patrol_right = 240.0f;
    config.enemy_start_x = 205.0f; config.enemy_feet_y = 224.0f;
    config.enemy_speed = 10.0f; config.sword_reach = 48.0f;
    config.contact_range = 8.0f;
    config.enemy_initial_hp = 2u; config.player_initial_hp = 3u;
    config.sword_cooldown_frames = 12u;
    config.hurt_cooldown_frames = 30u;

    if (hm_session_init(&world, &config, &game) != HM_SESSION_OK)
        return HM_REPLAY_INIT;
    for (frame = 0; frame < R_FRAMES; ++frame) {
        hm_input input = {0.0f, 0u, 0u};
        uint32_t x, feet;
        /* Fixed scripted inputs: run right, sword strike, reverse, jump,
           land and idle. Controller-independent and completely offline. */
        if (frame < 80u) input.axis = 1.0f;
        else if (frame < 120u) input.axis = -1.0f;
        if (frame == 100u) input.jump = 1u;
        if (hm_session_step(&world, &config, &game, input,
              (uint8_t)(frame == 70u), 1.0f / 60.0f) != HM_SESSION_OK)
            return HM_REPLAY_STEP;
        x = quantize_position(game.player.x);
        feet = quantize_position(game.player.feet_y);
        if (x == UINT32_MAX || feet == UINT32_MAX)
            return HM_REPLAY_INVARIANT;
        h = mix_u32(h, x);
        h = mix_u32(h, feet);
        h = mix_u32(h, game.player.picked);
        h = mix_u32(h, (uint32_t)game.player.checkpoint);
        h = mix_u32(h, game.combat.enemy_hp);
        h = mix_u32(h, game.combat.player_hp);
    }
    next.frames = game.player.frame;
    next.picked = game.player.picked;
    next.landings = game.player.landings;
    next.sword_hits = game.combat.sword_hits;
    next.respawns = game.player.respawns;
    next.fingerprint = h;
    /* A fingerprint alone is not proof of correctness. Require physical
       interaction with pickup and checkpoint, a completed jump and hit. */
    if (game.player.frame != R_FRAMES || game.combat.frame != R_FRAMES ||
        game.player.picked != 1u || game.player.checkpoint != 1 ||
        game.player.landings < 1u || game.combat.sword_hits < 1u ||
        game.player.respawns != 0u)
        return HM_REPLAY_INVARIANT;
    *out = next;
    return HM_REPLAY_OK;
}

hm_replay_status hm_replay_verify(hm_replay_report *out) {
    hm_replay_report first, second;
    hm_replay_status status;
    if (!out) return HM_REPLAY_BAD_ARGUMENT;
    status = hm_replay_run(&first);
    if (status != HM_REPLAY_OK) return status;
    status = hm_replay_run(&second);
    if (status != HM_REPLAY_OK) return status;
    if (first.fingerprint != second.fingerprint ||
        first.frames != second.frames || first.picked != second.picked ||
        first.landings != second.landings ||
        first.sword_hits != second.sword_hits ||
        first.respawns != second.respawns)
        return HM_REPLAY_MISMATCH;
    *out = first;
    return HM_REPLAY_OK;
}
