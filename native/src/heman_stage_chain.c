#include "heman_stage_chain.h"

int hm_chain_continue_edge_allowed(const hm_session *session, uint8_t stage,
                                   uint8_t paused, uint8_t minus_edge,
                                   uint8_t a_edge) {
    /* The two buttons may be asserted together in one real HID snapshot.
       Pausing must win, so no stage progress is consumed by that edge. */
    return session != 0 && stage == 0u && paused == 0u &&
           minus_edge == 0u && a_edge == 1u &&
           session->player.completed == 1u;
}

hm_chain_result hm_chain_try_advance(
    const hm_world *next_world, const hm_combat_config *next_combat,
    hm_session *session, uint8_t *stage, uint8_t continue_pressed) {
    hm_session fresh;
    if (!next_world || !next_combat || !session || !stage ||
        *stage > 1u || continue_pressed > 1u)
        return HM_CHAIN_INVALID;
    /* Pressing A cannot bypass original session completion; room 2 is the
       final authored test scene. No game frame is stepped on the edge. */
    if (!continue_pressed || *stage != 0u || session->player.completed != 1u)
        return HM_CHAIN_NOT_READY;
    if (hm_session_init(next_world, next_combat, &fresh) != HM_SESSION_OK)
        return HM_CHAIN_SETUP_ERROR;
    *session = fresh;
    *stage = 1u;
    return HM_CHAIN_ADVANCED;
}
