#ifndef HEMAN_SESSION_H
#define HEMAN_SESSION_H

#include "heman_core.h"
#include "heman_combat.h"

/* A minimal independent C99 adapter for the synthetic Switch course.
   The original iOS game is not represented by these rules or constants. */
typedef struct {
    hm_state player;
    hm_combat_state combat;
    uint8_t facing_right;
} hm_session;

typedef enum {
    HM_SESSION_OK = 0,
    HM_SESSION_INVALID = 1,
    HM_SESSION_PHYSICS_ERROR = 2,
    HM_SESSION_COMBAT_ERROR = 3
} hm_session_result;

/* These functions either commit the entire requested transition, or
   preserve the destination session byte-for-byte on failure. */
hm_session_result hm_session_init(const hm_world *world,
                                  const hm_combat_config *combat_cfg,
                                  hm_session *session);
hm_session_result hm_session_step(const hm_world *world,
                                  const hm_combat_config *combat_cfg,
                                  hm_session *session,
                                  hm_input movement,
                                  uint8_t attack_pressed,
                                  float dt);
#endif
