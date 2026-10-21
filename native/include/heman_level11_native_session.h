#ifndef HEMAN_LEVEL11_NATIVE_SESSION_H
#define HEMAN_LEVEL11_NATIVE_SESSION_H

#include "heman_level11_native_contacts.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Opt-in physics + lore session. World and its arrays are BORROWED,
 * immutable during a session, and must outlive this object. The event
 * bindings come from the caller; role validation is NOT proof of
 * original iOS ownership, geometry, collision semantics or footage.
 *
 * All state remains self-contained and zero-allocation. This is not
 * linked into the current stable 2-room or experimental 3-room NRO.
 */
typedef struct {
    const hm_world *world;
    hm_level11_event_bindings bindings;
    hm_state player;
    hm_lore_state lore;
    uint8_t attack_previous_down;
    uint8_t initialized;
} hm_level11_native_session;

/* A failed init leaves an existing output session byte-for-byte unchanged. */
hm_lore_result hm_level11_session_init(
    hm_level11_native_session *session, const hm_world *world,
    const hm_level11_event_bindings *bindings);

/* The ONLY attack event forwarded to stage104 is the rising edge
 * (attack_down == 1 && attack_previous_down == 0). Held attack across
 * multiple frames cannot cause additional fresh strikes; a release is
 * needed before a second attack. This does not verify original iOS
 * gesture input nor controller provenance: 'attack_down' is a caller
 * supplied button level, not a trusted hardware signal.
 *
 * The adapter runs hm_step on its OWN state and the stage104 verifier
 * independently replays it before committing game state. On invalid
 * input/step/event mapping, nothing, including the button latch,
 * is changed. Returns BLOCKED when no lore was earned even though
 * native movement advanced legitimately.
 */
hm_lore_result hm_level11_session_step(
    hm_level11_native_session *session, hm_input input, float dt,
    uint8_t attack_down);

/* Explicit caller-controlled upgrade: does not assert original upgrade
 * acquisition or purchase status. Reuses validated stage102 semantics. */
hm_lore_result hm_level11_session_grant_wall_crusher(
    hm_level11_native_session *session, uint8_t granted);

#ifdef __cplusplus
}
#endif
#endif
