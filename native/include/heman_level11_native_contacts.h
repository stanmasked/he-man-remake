#ifndef HEMAN_LEVEL11_NATIVE_CONTACTS_H
#define HEMAN_LEVEL11_NATIVE_CONTACTS_H

#include "heman_core.h"
#include "heman_level11_lore.h"

/* Independent event bindings, not assumed original iOS object indices.
 * Ownership and coordinates MUST be verified privately before gameplay use.
 * HM_TRIGGER represents a gate contact sensor, not damage to the obstacle;
 * a fresh attack edge is required in the SAME physics step to break it.
 */
typedef struct {
    uint32_t left_gate_event;     /* HM_TRIGGER */
    uint32_t skeletor_bio_event;  /* HM_PICKUP */
    uint32_t concept_art_event;   /* HM_PICKUP */
} hm_level11_event_bindings;

/* Verify the exact *existing* C99 hm_step before accepting sensor contact.
 * Input before/after must be consecutive genuine in-engine states. A forged
 * bitmap, changed frame counter, reset, different world or wrong event kind
 * cannot earn collectible progress. Attack edge is supplied separately by
 * the controller/attack subsystem; this verifier cannot authenticate its
 * provenance or the original iOS physics from metadata alone.
 *
 * No positions, game assets, events, or source-original geometry embedded.
 * The lore destination is changed only when the entire receipt is valid.
 * Return BLOCKED for no applicable new contact, INVALID for malformed data.
 */
hm_lore_result hm_level11_accept_native_frame(
    const hm_world *world, const hm_state *before, const hm_state *after,
    hm_input input, float dt, uint8_t attack_fresh_press,
    const hm_level11_event_bindings *bindings, hm_lore_state *lore);

#endif
