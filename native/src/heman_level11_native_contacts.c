#include "heman_level11_native_contacts.h"
#include <stdint.h>
#include <string.h>

/* 32 events maximum is part of the unmodified hm_core C99 ABI. */
static int binding_valid(const hm_world *w,
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
    return w->events[b->left_gate_event].kind == HM_TRIGGER &&
           w->events[b->skeletor_bio_event].kind == HM_PICKUP &&
           w->events[b->concept_art_event].kind == HM_PICKUP;
}

hm_lore_result hm_level11_accept_native_frame(
    const hm_world *world, const hm_state *before, const hm_state *after,
    hm_input input, float dt, uint8_t attack_fresh_press,
    const hm_level11_event_bindings *bindings, hm_lore_state *lore) {
    hm_state recomputed;
    hm_lore_state candidate;
    hm_lore_result result;
    uint32_t new_triggers, new_pickups;
    uint32_t gate_bit, bio_bit, art_bit;
    int applied = 0, already = 0;
    if (!before || !after || !lore || !binding_valid(world, bindings) ||
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

    new_triggers = after->triggered & ~before->triggered;
    new_pickups = after->picked & ~before->picked;
    gate_bit = UINT32_C(1) << bindings->left_gate_event;
    bio_bit = UINT32_C(1) << bindings->skeletor_bio_event;
    art_bit = UINT32_C(1) << bindings->concept_art_event;
    candidate = *lore;

    /* A fresh gate collision alone cannot break an obstacle: an actual
     * fresh attack command must coincide, and Wall Crusher be granted.
     * The native HM_TRIGGER is a movement contact sensor; future source-
     * validated integration must bind it to the proper collision fixture. */
    if ((new_triggers & gate_bit) && attack_fresh_press) {
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
