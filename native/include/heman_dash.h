#ifndef HEMAN_DASH_H
#define HEMAN_DASH_H
#include "heman_pause.h"

/* Optional second-room dash, independent synthetic mechanic. Does NOT
   reconstruct any original iOS behavior. 60-Hz, no allocations.
   A fresh ZR edge on the ground + horizontal direction gives twelve
   fast simulated frames, followed by an eighty-frame recovery. */
#define HM_DASH_DURATION_FRAMES 12u
#define HM_DASH_RECOVERY_FRAMES 80u

typedef struct {
    uint8_t remaining;
    uint16_t recovery;
} hm_dash_state;

/* Dash state changes only when a genuine physics/combat frame succeeded.
   Pauses, toggles and invalid input cannot consume dash frames or recovery.
   Invalid calls preserve session, dash and the pause flag byte-for-byte.
   Stop dashing immediately on respawn or explicit B retry.
   start_dash is a fresh ZR DOWN edge; ordinary held ZR does not repeat.
   World, physics and combat are borrowed and never mutated. */
hm_session_result hm_dash_session_step(
    const hm_world *world, const hm_combat_config *combat,
    hm_session *session, uint8_t *paused, hm_dash_state *dash,
    hm_input movement, uint8_t attack_pressed,
    uint8_t toggle_pause, uint8_t start_dash, float dt);

#endif
