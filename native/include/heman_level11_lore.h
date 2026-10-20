#ifndef HEMAN_LEVEL11_LORE_H
#define HEMAN_LEVEL11_LORE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Independent, location-agnostic LEVEL 1-1 objective adapter. Public
 * walkthrough documents two lore rewards but NOT original positions or
 * collision geometry. Caller must confirm contacts in the real scene.
 * No copyrighted art, original coordinates, original save data or IPA.
 */
typedef enum {
    HM_LORE_SKELETOR_BIO = 0,
    HM_LORE_CONCEPT_ART_09 = 1,
    HM_LORE_OBJECTIVE_COUNT = 2
} hm_lore_objective;

typedef enum {
    HM_LORE_INVALID = -1,        /* preserve state byte-for-byte */
    HM_LORE_BLOCKED = 0,         /* legal input, unmet precondition */
    HM_LORE_APPLIED = 1,         /* exactly one state transition */
    HM_LORE_ALREADY_DONE = 2    /* idempotent no-op */
} hm_lore_result;

typedef struct {
    uint8_t wall_crusher_unlocked;
    uint8_t left_gate_broken;
    uint8_t collected_mask;      /* bit 0: Bio Skeletor, bit 1: Concept Art 09 */
    uint8_t collected_count;
} hm_lore_state;

/* Initialises only destination memory, with deterministic no-allocation C99. */
hm_lore_result hm_lore_init(hm_lore_state *state);

/* The surrounding progression system (not implemented here) owns unlocks.
 * Requires explicit binary authorization, never infers a paid upgrade. */
hm_lore_result hm_lore_grant_wall_crusher(hm_lore_state *state,
                                          uint8_t granted);

/* Must be called ONLY after scene physics confirms an actual attack against
 * the correct gate; an unupgraded ordinary slash cannot open this barrier.
 * This module has no ability to assert positions, timers or line-of-sight. */
hm_lore_result hm_lore_attack_left_gate(hm_lore_state *state,
                                        uint8_t confirmed_contact);

/* Must be called ONLY after scene physics confirms player touches the lore.
 * The midway Concept Art 09 has no ability requirement; the left Skeletor
 * reward requires the independent Wall Crusher barrier to be opened. */
hm_lore_result hm_lore_collect(hm_lore_state *state,
                               hm_lore_objective target,
                               uint8_t confirmed_overlap);

/* Separate read-only snapshot validation; never mutates state. */
int hm_lore_state_valid(const hm_lore_state *state);
uint8_t hm_lore_remaining_mask(const hm_lore_state *state);

#ifdef __cplusplus
}
#endif
#endif
