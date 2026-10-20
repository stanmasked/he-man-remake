#ifndef HEMAN_PAUSE_H
#define HEMAN_PAUSE_H

#include "heman_session.h"

/* Portable, asset-free controller pause adapter for the synthetic Switch
   course. paused is 0/1. A pause toggle consumes its own frame; the entire
   physics/combat session is left byte-identical until the NEXT unpaused tick.
   No original iOS gameplay or pause semantics are claimed. */
hm_session_result hm_paused_session_step(
    const hm_world *world, const hm_combat_config *combat_cfg,
    hm_session *session, uint8_t *paused, hm_input movement,
    uint8_t attack_pressed, uint8_t toggle_pause, float dt);

#endif
