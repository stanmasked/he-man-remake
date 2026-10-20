#ifndef HEMAN_FINALE_H
#define HEMAN_FINALE_H

#include "heman_dash.h"

/* Optional original-content-free two-room training course.
   When room 2 earns HM_EXIT the completed session stays byte-identical
   under movement, attack, jump and ZR. B is an explicit restart. Minus
   toggles pause without stepping a frame, and Plus remains owned by libnx.
   Does not claim any behavior of the commercial iOS game. */
hm_session_result hm_finale_session_step(
    const hm_world *world, const hm_combat_config *combat,
    hm_session *session, uint8_t *paused, hm_dash_state *dash,
    uint8_t stage, hm_input movement, uint8_t attack_pressed,
    uint8_t toggle_pause, uint8_t start_dash, float dt);

#endif
