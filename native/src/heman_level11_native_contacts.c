#include "heman_level11_native_contacts.h"
#include <stdint.h>
#include <string.h>
#include <math.h>

/* 32 events maximum is part of the unmodified hm_core C99 ABI. */
int hm_level11_native_bindings_valid(const hm_world *w,
                                     const hm_level11_event_bindings *b) {
    if (!w || !b || !w->events || w->event_count < 3u ||
        w->event_count > 32u ||
        b->left_gate_event >= w->event_count ||
        b->skeletor_bio_event >= w->event_count ||
        b->concept_art_event >= w->event_count ||
        b->left_gate_event == b->skeletor_bio_event ||
        b->left_gate_event == b->concept_art_event ||
        b->skeletor_bio_event == b->concept_art_event)
        return 0;
    if (w->events[b->left_gate_event].kind != HM_TRIGGER ||
        w->events[b->skeletor_bio_event].kind != HM_PICKUP ||
        w->events[b->concept_art_event].kind != HM_PICKUP ||
        !isfinite(w->actor_half_width) ||
        !isfinite(w->actor_height) ||
        w->actor_half_width <= 0.0f || w->actor_height <= 0.0f)
        return 0;
    {
        uint32_t k;
        const uint32_t indexes[3] = {
            b->left_gate_event, b->skeletor_bio_event,
            b->concept_art_event
        };
        for (k = 0u; k < 3u; ++k) {
            const hm_event *e = &w->events[indexes[k]];
            if (!isfinite(e->x) || !isfinite(e->y) ||
                !isfinite(e->radius) || e->radius < 1.0f ||
                e->radius > 128.0f) return 0;
        }
    }
    return 1;
}

/* Same actor-body-vs-event-circle test as heman_core.c:touches().
 * This supplements the sticky HM_TRIGGER bit with evidence that the actor
 * is STILL at the gate when a fresh sword command is submitted. Therefore
 * the player can return later after obtaining Wall Crusher. No original
 * iOS obstacle coordinates are encoded here.
 */
static int at_sensor(const hm_world *w, const hm_state *s,
                     const hm_event *e) {
    const float dx = fmaxf(0.0f,
                         fabsf(e->x - s->x) - w->actor_half_width);
    const float top = s->feet_y - w->actor_height;
    const float dy = fmaxf(0.0f,
                         fmaxf(top - e->y, e->y - s->feet_y));
    return dx * dx + dy * dy <= e->radius * e->radius;
}

hm_lore_result hm_level11_accept_native_frame(
    const hm_world *world, const hm_state *before, const hm_state *after,
    hm_input input, float dt, uint8_t attack_fresh_press,
    const hm_level11_event_bindings *bindings, hm_lore_state *lore) {
    hm_state recomputed;
    hm_lore_state candidate;
    hm_lore_result result;
    uint32_t new_pickups;
    uint32_t gate_bit, bio_bit, art_bit;
    int applied = 0, already = 0;
    if (!before || !after || !lore || !hm_level11_native_bindings_valid(world, bindings) ||
        !hm_lore_state_valid(lore) || attack_fresh_press > 1u ||
        before->frame == UINT32_MAX)
        return HM_LORE_INVALID;

    /* A receipt based on supplied flags alone can be forged. Rerun the
     * actual deterministic game step, then compare the FULL native state:
     * counters, physics, event flags, camera, completion and frame ordinal.
     * No synthetic "contact=true" parameter is trusted. */
    recomputed = *before;
    if (hm_step(world, &recomputed, input, dt) != HM_OK ||
        memcmp(&recomputed, after, sizeof(recomputed)) != 0)
        return HM_LORE_INVALID;

    /* A reset/death/automatic respawn must never mint a lore reward. */
    if (input.reset || after->respawns != before->respawns ||
        after->hazards != before->hazards)
        return HM_LORE_BLOCKED;

    new_pickups = after->picked & ~before->picked;
    gate_bit = UINT32_C(1) << bindings->left_gate_event;
    bio_bit = UINT32_C(1) << bindings->skeletor_bio_event;
    art_bit = UINT32_C(1) << bindings->concept_art_event;
    candidate = *lore;

    /* HM_TRIGGER bits are sticky in hm_core. An attack must be fresh,
     * issued while the live physics body still touches the authored gate
     * sensor, and the sensor must actually be triggered by native physics.
     * This also permits returning after upgrading Wall Crusher; neither a
     * stale trigger alone nor a distant attack can break the obstacle.
     * The sensor must later be bound to verified original scene geometry. */
    if (attack_fresh_press && (after->triggered & gate_bit) &&
        at_sensor(world, after, &world->events[bindings->left_gate_event])) {
        result = hm_lore_attack_left_gate(&candidate, 1u);
        if (result == HM_LORE_INVALID) return HM_LORE_INVALID;
        applied |= result == HM_LORE_APPLIED;
        already |= result == HM_LORE_ALREADY_DONE;
    }
    if (new_pickups & bio_bit) {
        result = hm_lore_collect(&candidate, HM_LORE_SKELETOR_BIO, 1u);
        if (result == HM_LORE_INVALID) return HM_LORE_INVALID;
        applied |= result == HM_LORE_APPLIED;
        already |= result == HM_LORE_ALREADY_DONE;
    }
    if (new_pickups & art_bit) {
        result = hm_lore_collect(&candidate, HM_LORE_CONCEPT_ART_09, 1u);
        if (result == HM_LORE_INVALID) return HM_LORE_INVALID;
        applied |= result == HM_LORE_APPLIED;
        already |= result == HM_LORE_ALREADY_DONE;
    }

    if (!hm_lore_state_valid(&candidate)) return HM_LORE_INVALID;
    if (!applied) return already ? HM_LORE_ALREADY_DONE : HM_LORE_BLOCKED;
    *lore = candidate; /* Commit only fully validated frame effects. */
    return HM_LORE_APPLIED;
}
