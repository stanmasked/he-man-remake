#include "heman_three_room_chain.h"

int hm_three_room_continue_allowed(
    const hm_session *session, uint8_t stage, uint8_t paused,
    uint8_t minus_edge, uint8_t a_edge) {
    return session != 0 && stage < 2u && paused == 0u &&
           minus_edge == 0u && a_edge == 1u &&
           session->player.completed == 1u;
}

hm_chain_result hm_three_room_try_advance(
    const hm_world *next_world, const hm_combat_config *next_combat,
    hm_session *session, uint8_t *stage, uint8_t continue_pressed) {
    hm_session fresh;
    if (!next_world || !next_combat || !session || !stage ||
        *stage > 2u || continue_pressed > 1u)
        return HM_CHAIN_INVALID;
    if (!continue_pressed || *stage == 2u ||
        session->player.completed != 1u)
        return HM_CHAIN_NOT_READY;
    if (hm_session_init(next_world, next_combat, &fresh) != HM_SESSION_OK)
        return HM_CHAIN_SETUP_ERROR;
    *session = fresh;
    *stage = (uint8_t)(*stage + 1u);
    return HM_CHAIN_ADVANCED;
}
