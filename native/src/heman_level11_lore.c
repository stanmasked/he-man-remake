#include "heman_level11_lore.h"
#include <string.h>

#define HM_LORE_BITS ((uint8_t)0x03u)

int hm_lore_state_valid(const hm_lore_state *state) {
    unsigned count;
    if (!state || state->wall_crusher_unlocked > 1u ||
        state->left_gate_broken > 1u ||
        (state->collected_mask & (uint8_t)~HM_LORE_BITS) != 0u)
        return 0;
    if (state->left_gate_broken && !state->wall_crusher_unlocked)
        return 0;
    if ((state->collected_mask & 1u) && !state->left_gate_broken)
        return 0;
    count = ((state->collected_mask & 1u) != 0u) +
            ((state->collected_mask & 2u) != 0u);
    return state->collected_count == count;
}

hm_lore_result hm_lore_init(hm_lore_state *state) {
    if (!state) return HM_LORE_INVALID;
    memset(state, 0, sizeof(*state));
    return HM_LORE_APPLIED;
}

hm_lore_result hm_lore_grant_wall_crusher(hm_lore_state *state,
                                          uint8_t granted) {
    if (!hm_lore_state_valid(state) || granted > 1u)
        return HM_LORE_INVALID;
    if (!granted) return HM_LORE_BLOCKED;
    if (state->wall_crusher_unlocked) return HM_LORE_ALREADY_DONE;
    state->wall_crusher_unlocked = 1u;
    return HM_LORE_APPLIED;
}

hm_lore_result hm_lore_attack_left_gate(hm_lore_state *state,
                                        uint8_t confirmed_contact) {
    if (!hm_lore_state_valid(state) || confirmed_contact > 1u)
        return HM_LORE_INVALID;
    if (!confirmed_contact) return HM_LORE_BLOCKED;
    if (state->left_gate_broken) return HM_LORE_ALREADY_DONE;
    if (!state->wall_crusher_unlocked) return HM_LORE_BLOCKED;
    state->left_gate_broken = 1u;
    return HM_LORE_APPLIED;
}

hm_lore_result hm_lore_collect(hm_lore_state *state,
                               hm_lore_objective target,
                               uint8_t confirmed_overlap) {
    uint8_t bit;
    if (!hm_lore_state_valid(state) || confirmed_overlap > 1u ||
        (target != HM_LORE_SKELETOR_BIO &&
         target != HM_LORE_CONCEPT_ART_09))
        return HM_LORE_INVALID;
    if (!confirmed_overlap) return HM_LORE_BLOCKED;
    bit = (uint8_t)(1u << (unsigned)target);
    if ((state->collected_mask & bit) != 0u) return HM_LORE_ALREADY_DONE;
    if (target == HM_LORE_SKELETOR_BIO && !state->left_gate_broken)
        return HM_LORE_BLOCKED;
    state->collected_mask = (uint8_t)(state->collected_mask | bit);
    state->collected_count++;
    return HM_LORE_APPLIED;
}

uint8_t hm_lore_remaining_mask(const hm_lore_state *state) {
    if (!hm_lore_state_valid(state)) return 0xffu;
    return (uint8_t)(HM_LORE_BITS & (uint8_t)~state->collected_mask);
}
