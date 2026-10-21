/* Stage104: real synthetic native hm_step frames, never source iOS geometry.
 * Verifies that the lore contact adapter cannot be bypassed by forged
 * picked/triggered bits, wrong event IDs or mismatched native physics.
 */
#include "heman_level11_native_contacts.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CW 32u
#define CH 12u
#define DT (1.0f / 60.0f)

static uint8_t cells[CW * CH];
static hm_event events[3] = {
    {HM_TRIGGER, 104.0f, 114.0f, 4.0f}, /* synthetic left gate sensor */
    {HM_PICKUP, 148.0f, 114.0f, 4.0f},  /* synthetic Bio */
    {HM_PICKUP, 56.0f, 114.0f, 4.0f},   /* synthetic open Concept Art */
};
static const hm_level11_event_bindings bindings = {0u, 1u, 2u};

static hm_world world_init(void) {
    hm_world w;
    uint32_t x;
    memset(&w, 0, sizeof(w));
    memset(cells, 0, sizeof(cells));
    for (x = 0u; x < CW; ++x) cells[8u * CW + x] = 1u;
    w.solid = cells;
    w.columns = CW; w.rows = CH; w.tile_size = 16u;
    w.spawn_x = 24.0f; w.spawn_feet_y = 128.0f;
    w.actor_half_width = 5.0f; w.actor_height = 20.0f;
    w.speed = 120.0f; w.gravity = 1200.0f; w.jump_speed = 420.0f;
    w.terminal_speed = 1400.0f;
    w.viewport_width = 320.0f; w.viewport_height = 192.0f;
    w.death_margin = 96.0f;
    w.events = events; w.event_count = 3u;
    return w;
}
static void unmodified(const hm_lore_state *a, const hm_lore_state *b) {
    assert(memcmp(a, b, sizeof(*a)) == 0);
}
static hm_input move_right(void) {
    hm_input input = {1.0f, 0u, 0u};
    return input;
}
static hm_lore_result native_frame(const hm_world *w, hm_state *s,
                                   hm_lore_state *lore, uint8_t attack,
                                   hm_state *before_out, hm_state *after_out) {
    hm_input input = move_right();
    hm_state before = *s;
    hm_lore_result result;
    assert(hm_step(w, s, input, DT) == HM_OK);
    result = hm_level11_accept_native_frame(
        w, &before, s, input, DT, attack, &bindings, lore);
    if (before_out) *before_out = before;
    if (after_out) *after_out = *s;
    return result;
}

static void test_true_native_route_both_rewards_in_any_order(void) {
    unsigned order;
    for (order = 0u; order < 2u; ++order) {
        hm_world w = world_init();
        hm_state player;
        hm_lore_state lore;
        hm_lore_result result;
        unsigned n, gate_hits = 0u, art_hits = 0u, bio_hits = 0u;
        assert(hm_init(&w, &player) == HM_OK);
        assert(hm_lore_init(&lore) == HM_LORE_APPLIED);
        if (order == 0u)
            assert(hm_lore_grant_wall_crusher(&lore, 1u) == HM_LORE_APPLIED);
        for (n = 0u; n < 78u; ++n) {
            hm_state before;
            hm_input in = move_right();
            uint8_t fresh_attack;
            before = player;
            assert(hm_step(&w, &player, in, DT) == HM_OK);
            fresh_attack = (uint8_t)((player.triggered & ~before.triggered & 1u)
                                      != 0u);
            if (order == 1u && fresh_attack) {
                /* The gameplay unlock was not granted before the first gate
                   collision. Native movement alone must never break it. */
                hm_lore_state saved = lore;
                result = hm_level11_accept_native_frame(
                    &w, &before, &player, in, DT, fresh_attack, &bindings, &lore);
                assert(result == HM_LORE_BLOCKED);
                unmodified(&saved, &lore);
                assert(hm_lore_grant_wall_crusher(&lore, 1u) == HM_LORE_APPLIED);
            } else {
                result = hm_level11_accept_native_frame(
                    &w, &before, &player, in, DT, fresh_attack, &bindings, &lore);
                assert(result != HM_LORE_INVALID);
            }
            if (player.triggered & 1u) gate_hits++;
            if (lore.collected_mask & 2u) art_hits++;
            if (lore.collected_mask & 1u) bio_hits++;
        }
        assert(gate_hits && art_hits);
        if (order == 0u) {
            assert(bio_hits);
            assert(lore.wall_crusher_unlocked == 1u);
            assert(lore.left_gate_broken == 1u);
            assert(lore.collected_mask == 3u && lore.collected_count == 2u);
        } else {
            /* Touching a blocked gate BEFORE obtaining the upgrade cannot
             * retroactively mint its hidden collectible. Need new sensor
             * contact in a later independently verified frame. */
            assert(bio_hits == 0u);
            assert(lore.wall_crusher_unlocked == 1u);
            assert(lore.left_gate_broken == 0u);
            assert(lore.collected_mask == 2u && lore.collected_count == 1u);
        }
        assert(lore.collected_count <= 2u);
    }
}

static void test_no_fresh_attack_cannot_open_gate(void) {
    hm_world w = world_init();
    hm_state player;
    hm_lore_state lore;
    unsigned n;
    assert(hm_init(&w, &player) == HM_OK);
    assert(hm_lore_init(&lore) == HM_LORE_APPLIED);
    assert(hm_lore_grant_wall_crusher(&lore, 1u) == HM_LORE_APPLIED);
    for (n = 0u; n < 76u; ++n)
        assert(native_frame(&w, &player, &lore, 0u, NULL, NULL) != HM_LORE_INVALID);
    assert(player.triggered & 1u);
    assert(player.picked & 2u); /* simulated player walked through gate */
    assert(lore.left_gate_broken == 0u);
    assert((lore.collected_mask & 1u) == 0u);
    assert((lore.collected_mask & 2u) != 0u);
}

static void test_forged_full_state_and_bad_binding_fail_atomically(void) {
    hm_world w = world_init();
    hm_state player, before, after;
    hm_lore_state lore, saved;
    hm_level11_event_bindings b = bindings;
    hm_input in = move_right();
    assert(hm_init(&w, &player) == HM_OK);
    assert(hm_lore_init(&lore) == HM_LORE_APPLIED);
    before = player;
    assert(hm_step(&w, &player, in, DT) == HM_OK);
    after = player;
    saved = lore;
    after.picked |= 1u << b.skeletor_bio_event; /* fake pickup */
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 0u, &b, &lore)
           == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    after = player;
    after.triggered |= 1u << b.left_gate_event; /* fake gate sensor */
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 1u, &b, &lore)
           == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    after = player;
    after.x += 1.0f;
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 1u, &b, &lore)
           == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    after = player;
    after.frame++;
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 1u, &b, &lore)
           == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    after = player;
    b.left_gate_event = 1u; /* pickup is NOT gate trigger */
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 0u, &b, &lore)
           == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    b = bindings;
    b.concept_art_event = b.skeletor_bio_event;
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 0u, &b, &lore)
           == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    b = bindings;
    b.skeletor_bio_event = 32u;
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 0u, &b, &lore)
           == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    b = bindings;
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 2u, &b, &lore)
           == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 0u, NULL, &lore)
           == HM_LORE_INVALID);
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 0u, &b, NULL)
           == HM_LORE_INVALID);
}

static void test_wrong_input_timing_and_reset_rejected(void) {
    hm_world w = world_init();
    hm_state player, before;
    hm_lore_state lore, saved;
    hm_input in = move_right(), wrong = {0.0f, 0u, 0u};
    assert(hm_init(&w, &player) == HM_OK);
    assert(hm_lore_init(&lore) == HM_LORE_APPLIED);
    before = player;
    assert(hm_step(&w, &player, in, DT) == HM_OK);
    saved = lore;
    assert(hm_level11_accept_native_frame(&w, &before, &player, wrong, DT, 0u,
                                           &bindings, &lore) == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    assert(hm_level11_accept_native_frame(&w, &before, &player, in, -DT, 0u,
                                           &bindings, &lore) == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    assert(hm_level11_accept_native_frame(&w, &before, &player, in, NAN, 0u,
                                           &bindings, &lore) == HM_LORE_INVALID);
    unmodified(&saved, &lore);
    in.reset = 1u;
    before = player;
    assert(hm_step(&w, &player, in, DT) == HM_OK);
    assert(hm_level11_accept_native_frame(&w, &before, &player, in, DT, 0u,
                                           &bindings, &lore) == HM_LORE_BLOCKED);
    unmodified(&saved, &lore);
}

static void test_no_reaward_on_replayed_receipt(void) {
    hm_world w = world_init();
    hm_state player, before = {0}, after = {0};
    hm_lore_state lore, saved;
    hm_input in = move_right();
    unsigned n;
    int saw = 0;
    assert(hm_init(&w, &player) == HM_OK);
    assert(hm_lore_init(&lore) == HM_LORE_APPLIED);
    for (n = 0u; n < 35u; ++n) {
        hm_lore_result r;
        before = player;
        assert(hm_step(&w, &player, in, DT) == HM_OK);
        after = player;
        r = hm_level11_accept_native_frame(&w, &before, &after, in, DT, 0u,
                                            &bindings, &lore);
        if (r == HM_LORE_APPLIED) {
            assert(lore.collected_mask == 2u);
            saw = 1;
            break;
        }
    }
    assert(saw);
    saved = lore;
    assert(hm_level11_accept_native_frame(&w, &before, &after, in, DT, 0u,
                                           &bindings, &lore) == HM_LORE_ALREADY_DONE);
    unmodified(&saved, &lore);
}

int main(void) {
    test_true_native_route_both_rewards_in_any_order();
    test_no_fresh_attack_cannot_open_gate();
    test_forged_full_state_and_bad_binding_fail_atomically();
    test_wrong_input_timing_and_reset_rejected();
    test_no_reaward_on_replayed_receipt();
    puts("PASS: Stage104 exact native hm_step contact replay, real C99 "
         "event bindings, attack-gated reward, atomic forgery/replay resistance");
    puts("Fictional local geometry only, original iOS scene unverified");
    return 0;
}
