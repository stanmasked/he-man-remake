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
 * To reject accidental in-place map or event mutation, the opt-in session
 * checks borrowed fixture pointer identity, exact event-to-reward
 * bindings, and a full content checksum before each step and upgrade. This is not a cryptographic authentication
 * or proof that fixtures originated in the user's original iOS IPA.
 *
 * All state remains self-contained and zero-allocation. This is not
 * linked into the current stable 2-room or experimental 3-room NRO.
 */
typedef struct {
    const hm_world *world;
    /* A copied hm_world descriptor with identical arrays is not the
     * originally borrowed descriptor: do not silently switch ownership. */
    const hm_world *sealed_world;
    /* Record borrowed fixture identities and a non-cryptographic content
     * guard at init. No original map data is stored or serialized. */
    const hm_event *sealed_events;
    const uint8_t *sealed_solid;
    const hm_mask_grid *sealed_mask;
    const uint16_t *sealed_tile_ids;
    const uint64_t *sealed_mask_rows;
    uint64_t world_seal;
    uint32_t sealed_columns, sealed_rows, sealed_tile_size;
    uint32_t sealed_event_count, sealed_mask_count;
    hm_level11_event_bindings bindings;
    /* Binding roles are sealed separately from the world fingerprint:
     * both lore targets have kind HM_PICKUP and may be swapped while
     * still passing structural event-kind validation. */
    hm_level11_event_bindings sealed_bindings;
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

/* Read-only validity guard, including Stage106/107 world and role seals.
 * Useful for optional same-world replay snapshot processing. */
int hm_level11_session_valid(const hm_level11_native_session *session);

#ifdef __cplusplus
}
#endif
#endif
