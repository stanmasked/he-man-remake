#ifndef HEMAN_THREE_ROOM_CHAIN_H
#define HEMAN_THREE_ROOM_CHAIN_H

#include "heman_stage_chain.h"

/* Optional source-authored three-room training chain: 0 -> 1 -> 2.
   Existing two-room stage chain remains unchanged.
   Last room is terminal; room transitions require actual HM_EXIT + A.
   A transition is transactional and does not advance simulation. */
int hm_three_room_continue_allowed(
    const hm_session *session, uint8_t stage, uint8_t paused,
    uint8_t minus_edge, uint8_t a_edge);

hm_chain_result hm_three_room_try_advance(
    const hm_world *next_world, const hm_combat_config *next_combat,
    hm_session *session, uint8_t *stage, uint8_t continue_pressed);

#endif
