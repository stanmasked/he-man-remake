#ifndef HEMAN_AIR_SMASH_H
#define HEMAN_AIR_SMASH_H

#include "heman_finale.h"

/* Provisional synthetic aerial strike for opt-in Switch training only.
   This does NOT reproduce original iOS Aerial Smash/physics/hitboxes.
   ZL is a fresh edge, accepted in room 2 only while airborne and with
   cooldown complete. A successful activation accelerates native falling;
   landing emits 8 rendered feedback frames, and an enemy close to the
   landing position may take ONE point of damage. All updates are atomic. */
#define HM_SMASH_COOLDOWN_FRAMES 50u
#define HM_SMASH_FEEDBACK_FRAMES 8u
#define HM_SMASH_DROP_SPEED 520.0f
#define HM_SMASH_HIT_DISTANCE 24.0f

typedef struct {
    uint8_t armed;
    uint8_t impact_frames;
    uint16_t cooldown;
    uint32_t impacts;
    uint32_t enemy_hits;
} hm_air_smash_state;

hm_session_result hm_air_smash_step(
    const hm_world *world, const hm_combat_config *combat,
    hm_session *session, uint8_t *paused, hm_dash_state *dash,
    hm_air_smash_state *ability, uint8_t stage, hm_input movement,
    uint8_t attack_pressed, uint8_t toggle_pause, uint8_t start_dash,
    uint8_t start_smash, float dt);

#endif
