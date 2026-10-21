/* Stage102: first reference-guided level 1-1 lore rules, synthetic events.
 * Not original iOS map or collision / no commercial data or fake footage.
 */
#include "heman_level11_lore.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void same(const hm_lore_state *before,
                 const hm_lore_state *after) {
    assert(memcmp(before, after, sizeof(*before)) == 0);
}
static void test_unupgraded_left_gate_cannot_be_bypassed(void) {
    hm_lore_state state, before;
    assert(hm_lore_init(&state) == HM_LORE_APPLIED);
    before = state;
    assert(hm_lore_collect(&state, HM_LORE_SKELETOR_BIO, 1u) == HM_LORE_BLOCKED);
    same(&before, &state);
    assert(hm_lore_attack_left_gate(&state, 1u) == HM_LORE_BLOCKED);
    same(&before, &state);
    assert(hm_lore_grant_wall_crusher(&state, 0u) == HM_LORE_BLOCKED);
    same(&before, &state);
    assert(hm_lore_remaining_mask(&state) == 3u);
}
static void test_open_middle_lore_available_without_upgrade(void) {
    hm_lore_state state, before;
    assert(hm_lore_init(&state) == HM_LORE_APPLIED);
    assert(hm_lore_collect(&state, HM_LORE_CONCEPT_ART_09, 0u) == HM_LORE_BLOCKED);
    assert(hm_lore_collect(&state, HM_LORE_CONCEPT_ART_09, 1u) == HM_LORE_APPLIED);
    assert(state.collected_mask == 2u && state.collected_count == 1u);
    assert(state.wall_crusher_unlocked == 0u && state.left_gate_broken == 0u);
    before = state;
    assert(hm_lore_collect(&state, HM_LORE_CONCEPT_ART_09, 1u) ==
           HM_LORE_ALREADY_DONE);
    same(&before, &state);
    assert(hm_lore_remaining_mask(&state) == 1u);
}
static void test_unlock_break_and_collect_in_both_orders(void) {
    unsigned order;
    for (order = 0u; order < 2u; ++order) {
        hm_lore_state state, before;
        assert(hm_lore_init(&state) == HM_LORE_APPLIED);
        if (order == 0u)
            assert(hm_lore_collect(&state, HM_LORE_CONCEPT_ART_09, 1u) ==
                   HM_LORE_APPLIED);
        assert(hm_lore_grant_wall_crusher(&state, 1u) == HM_LORE_APPLIED);
        before = state;
        assert(hm_lore_attack_left_gate(&state, 0u) == HM_LORE_BLOCKED);
        same(&before, &state);
        assert(hm_lore_collect(&state, HM_LORE_SKELETOR_BIO, 1u) ==
               HM_LORE_BLOCKED);
        same(&before, &state);
        assert(hm_lore_attack_left_gate(&state, 1u) == HM_LORE_APPLIED);
        assert(state.left_gate_broken == 1u);
        assert(hm_lore_collect(&state, HM_LORE_SKELETOR_BIO, 1u) ==
               HM_LORE_APPLIED);
        if (order == 1u)
            assert(hm_lore_collect(&state, HM_LORE_CONCEPT_ART_09, 1u) ==
                   HM_LORE_APPLIED);
        assert(state.collected_count == 2u && state.collected_mask == 3u);
        assert(hm_lore_remaining_mask(&state) == 0u);
        before = state;
        assert(hm_lore_grant_wall_crusher(&state, 1u) == HM_LORE_ALREADY_DONE);
        assert(hm_lore_attack_left_gate(&state, 1u) == HM_LORE_ALREADY_DONE);
        assert(hm_lore_collect(&state, HM_LORE_SKELETOR_BIO, 1u) ==
               HM_LORE_ALREADY_DONE);
        same(&before, &state);
    }
}
static void test_invalid_arguments_are_atomic(void) {
    hm_lore_state state, before;
    assert(hm_lore_init(NULL) == HM_LORE_INVALID);
    assert(hm_lore_init(&state) == HM_LORE_APPLIED);
    before = state;
    assert(hm_lore_grant_wall_crusher(NULL, 1u) == HM_LORE_INVALID);
    assert(hm_lore_attack_left_gate(NULL, 1u) == HM_LORE_INVALID);
    assert(hm_lore_collect(NULL, HM_LORE_SKELETOR_BIO, 1u) == HM_LORE_INVALID);
    assert(hm_lore_grant_wall_crusher(&state, 2u) == HM_LORE_INVALID);
    assert(hm_lore_attack_left_gate(&state, 2u) == HM_LORE_INVALID);
    assert(hm_lore_collect(&state, HM_LORE_CONCEPT_ART_09, 2u) ==
           HM_LORE_INVALID);
    assert(hm_lore_collect(&state, (hm_lore_objective)-1, 1u) ==
           HM_LORE_INVALID);
    assert(hm_lore_collect(&state, (hm_lore_objective)2, 1u) ==
           HM_LORE_INVALID);
    same(&before, &state);
    assert(hm_lore_remaining_mask(NULL) == 0xffu);
}
static void test_reject_forged_or_impossible_saved_state(void) {
    hm_lore_state state, before;
    static const hm_lore_state broken[] = {
        {0u, 1u, 0u, 0u}, /* broken wall without upgrade */
        {0u, 0u, 1u, 1u}, /* collected reward behind intact wall */
        {1u, 0u, 1u, 1u}, /* upgrade alone does not open wall */
        {1u, 1u, 4u, 1u}, /* unknown lore token */
        {1u, 1u, 3u, 1u}, /* count does not match picked mask */
        {2u, 0u, 0u, 0u}, /* non-binary unlock */
        {1u, 2u, 0u, 0u}, /* non-binary obstacle flag */
    };
    unsigned k;
    assert(!hm_lore_state_valid(NULL));
    for (k = 0u; k < sizeof(broken)/sizeof(broken[0]); ++k) {
        state = broken[k];
        before = state;
        assert(!hm_lore_state_valid(&state));
        assert(hm_lore_grant_wall_crusher(&state, 1u) == HM_LORE_INVALID);
        assert(hm_lore_attack_left_gate(&state, 1u) == HM_LORE_INVALID);
        assert(hm_lore_collect(&state, HM_LORE_CONCEPT_ART_09, 1u) ==
               HM_LORE_INVALID);
        assert(hm_lore_remaining_mask(&state) == 0xffu);
        same(&before, &state);
    }
}
static void test_restart_is_explicit_not_assumed_original_save_behavior(void) {
    hm_lore_state state, previous;
    assert(hm_lore_init(&state) == HM_LORE_APPLIED);
    assert(hm_lore_collect(&state, HM_LORE_CONCEPT_ART_09, 1u) == HM_LORE_APPLIED);
    previous = state;
    assert(hm_lore_init(&state) == HM_LORE_APPLIED);
    assert(state.collected_count == 0u && state.collected_mask == 0u);
    assert(previous.collected_mask == 2u);
    /* Caller decides whether to keep previous across replay. We do not
       invent original iOS persistence or grant a reward twice. */
}
int main(void) {
    test_unupgraded_left_gate_cannot_be_bypassed();
    test_open_middle_lore_available_without_upgrade();
    test_unlock_break_and_collect_in_both_orders();
    test_invalid_arguments_are_atomic();
    test_reject_forged_or_impossible_saved_state();
    test_restart_is_explicit_not_assumed_original_save_behavior();
    puts("PASS: level1-1 source-reference lore gating, idempotent collectibles, "
         "atomic rollback and invalid-state validation (synthetic C99)");
    return 0;
}
