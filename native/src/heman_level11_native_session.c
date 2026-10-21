#include "heman_level11_native_session.h"
#include <string.h>

static int ready(const hm_level11_native_session *session) {
    return session && session->initialized == 1u &&
           session->attack_previous_down <= 1u &&
           hm_level11_native_bindings_valid(session->world,
                                             &session->bindings) &&
           hm_lore_state_valid(&session->lore);
}

hm_lore_result hm_level11_session_init(
    hm_level11_native_session *session, const hm_world *world,
    const hm_level11_event_bindings *bindings) {
    hm_level11_native_session candidate;
    if (!session || !hm_level11_native_bindings_valid(world, bindings))
        return HM_LORE_INVALID;
    memset(&candidate, 0, sizeof(candidate));
    candidate.world = world;
    candidate.bindings = *bindings;
    if (hm_init(world, &candidate.player) != HM_OK ||
        hm_lore_init(&candidate.lore) != HM_LORE_APPLIED)
        return HM_LORE_INVALID;
    candidate.initialized = 1u;
    *session = candidate;
    return HM_LORE_APPLIED;
}

hm_lore_result hm_level11_session_step(
    hm_level11_native_session *session, hm_input input, float dt,
    uint8_t attack_down) {
    hm_level11_native_session next;
    hm_state before;
    hm_lore_result result;
    uint8_t fresh;
    if (!ready(session) || attack_down > 1u ||
        input.jump > 1u || input.reset > 1u)
        return HM_LORE_INVALID;
    next = *session;
    before = next.player;
    fresh = (uint8_t)(attack_down && !next.attack_previous_down);
    if (hm_step(next.world, &next.player, input, dt) != HM_OK)
        return HM_LORE_INVALID;
    result = hm_level11_accept_native_frame(
        next.world, &before, &next.player, input, dt,
        fresh, &next.bindings, &next.lore);
    if (result == HM_LORE_INVALID)
        return HM_LORE_INVALID;
    next.attack_previous_down = attack_down;
    *session = next;
    return result;
}

hm_lore_result hm_level11_session_grant_wall_crusher(
    hm_level11_native_session *session, uint8_t granted) {
    hm_level11_native_session next;
    hm_lore_result result;
    if (!ready(session)) return HM_LORE_INVALID;
    next = *session;
    result = hm_lore_grant_wall_crusher(&next.lore, granted);
    if (result == HM_LORE_APPLIED)
        *session = next;
    return result;
}
