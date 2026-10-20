#ifndef HEMAN_STAGE_CHAIN_H
#define HEMAN_STAGE_CHAIN_H

#include "heman_session.h"

/* Independent 2-room campaign experiment; no data or mechanics from iOS.
   Session and stage commit together only when a source-authored room was
   cleared and the player presses A; no automatic level advance. */
typedef enum {
    HM_CHAIN_NOT_READY = 0,
    HM_CHAIN_ADVANCED = 1,
    HM_CHAIN_INVALID = 2,
    HM_CHAIN_SETUP_ERROR = 3
} hm_chain_result;

/* stage: 0 first room, 1 final room. All failed or ignored calls leave
   both stage and gameplay session unchanged byte-for-byte. */
hm_chain_result hm_chain_try_advance(
    const hm_world *next_world, const hm_combat_config *next_combat,
    hm_session *session, uint8_t *stage, uint8_t continue_pressed);

#endif
