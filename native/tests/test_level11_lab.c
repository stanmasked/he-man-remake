/* These EXACT tutorial-world/input functions are also linked into the
 * optional libnx Switch NRO. All scene events/graphics are synthetic.
 */
#include "heman_level11_lab.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint8_t solids[HM_LORE_LAB_CELLS];
static hm_world world;
static hm_level11_native_session game;
static hm_level11_lab_save save;

static void boot(void) {
    memset(&save, 0, sizeof(save));
    assert(hm_level11_lab_init(&world, solids, sizeof(solids), &game)
           == HM_LORE_APPLIED);
    assert(world.columns==32u && world.rows==12u);
    assert(world.event_count==3u);
    assert(hm_level11_session_valid(&game));
}
static hm_lore_result tick(uint32_t held, uint32_t down) {
    return hm_level11_lab_tick(&game,&save,held,down);
}
static void walk(uint32_t direction, unsigned count) {
    unsigned i;
    for(i=0u;i<count;++i)
        assert(tick(direction,0u)!=HM_LORE_INVALID);
}
static void no_change(const hm_level11_native_session *before,
                      const hm_level11_lab_save *saved) {
    assert(memcmp(before,&game,sizeof(game))==0);
    assert(memcmp(saved,&save,sizeof(save))==0);
}

static void test_source_native_lore_route_survives_save_restore(void) {
    hm_level11_native_session original;
    uint8_t original_snapshot[HM_LEVEL11_SNAPSHOT_SIZE];
    unsigned i;
    boot();
    walk(HM_LAB_RIGHT,73u);
    assert(game.player.x>165.0f);
    assert(game.player.picked & 2u);  /* touched hidden Bio too early */
    assert(game.player.triggered & 1u);
    assert(game.lore.collected_mask==2u); /* un-gated Concept Art 09 */
    assert(game.lore.collected_count==1u);
    assert(tick(HM_LAB_SAVE,HM_LAB_SAVE)==HM_LORE_APPLIED);
    assert(save.valid==1u);
    memcpy(original_snapshot,save.data,sizeof(original_snapshot));
    original=game;
    assert(tick(HM_LAB_RESET,HM_LAB_RESET)==HM_LORE_APPLIED);
    assert(game.player.frame==0u);
    assert(game.lore.collected_count==0u);
    assert(save.valid==1u);
    assert(tick(HM_LAB_LOAD,HM_LAB_LOAD)==HM_LORE_APPLIED);
    assert(game.player.x==original.player.x);
    assert(game.player.frame==original.player.frame);
    assert(game.lore.collected_mask==2u);
    assert(memcmp(save.data,original_snapshot,sizeof(original_snapshot))==0);

    assert(tick(HM_LAB_WALL_UPGRADE,HM_LAB_WALL_UPGRADE)==HM_LORE_APPLIED);
    assert(game.lore.wall_crusher_unlocked==1u);
    /* Old gate trigger bit alone cannot break the gate at x170. */
    assert(tick(HM_LAB_ATTACK,HM_LAB_ATTACK)==HM_LORE_BLOCKED);
    assert(game.lore.left_gate_broken==0u);
    assert(tick(0u,0u)==HM_LORE_BLOCKED);
    walk(HM_LAB_LEFT,31u);
    assert(game.player.x>96.0f && game.player.x<115.0f);
    assert(tick(HM_LAB_ATTACK,HM_LAB_ATTACK)==HM_LORE_APPLIED);
    assert(game.lore.left_gate_broken==1u);
    assert(tick(0u,0u)==HM_LORE_BLOCKED);
    walk(HM_LAB_RIGHT,32u);
    assert(game.lore.collected_mask==3u);
    assert(game.lore.collected_count==2u);
    assert(tick(HM_LAB_SAVE,HM_LAB_SAVE)==HM_LORE_APPLIED);
    assert(tick(HM_LAB_LOAD,HM_LAB_LOAD)==HM_LORE_APPLIED);
    for(i=0u;i<20u;++i)assert(tick(0u,0u)!=HM_LORE_INVALID);
    assert(game.lore.collected_count==2u);
}

static void test_attack_held_from_spawn_requires_release_at_gate(void) {
    boot();
    assert(tick(HM_LAB_WALL_UPGRADE,HM_LAB_WALL_UPGRADE)==HM_LORE_APPLIED);
    assert(tick(HM_LAB_ATTACK,HM_LAB_ATTACK)==HM_LORE_BLOCKED);
    {
        unsigned i;
        for(i=0u;i<41u;++i)
            assert(tick(HM_LAB_RIGHT|HM_LAB_ATTACK,0u)!=HM_LORE_INVALID);
    }
    assert(game.player.triggered & 1u);
    assert(game.lore.left_gate_broken==0u);
    assert(game.attack_previous_down==1u);
    assert(tick(0u,0u)==HM_LORE_BLOCKED);
    assert(tick(HM_LAB_ATTACK,HM_LAB_ATTACK)==HM_LORE_APPLIED);
    assert(game.lore.left_gate_broken==1u);
    assert(tick(HM_LAB_ATTACK,0u)==HM_LORE_BLOCKED);
    assert(game.lore.left_gate_broken==1u);
}

static void test_missing_and_corrupted_restore_are_atomic(void) {
    hm_level11_native_session previous;
    hm_level11_lab_save old;
    boot();
    previous=game;old=save;
    assert(tick(HM_LAB_LOAD,HM_LAB_LOAD)==HM_LORE_BLOCKED);
    no_change(&previous,&old);
    assert(tick(HM_LAB_SAVE,HM_LAB_SAVE)==HM_LORE_APPLIED);
    save.data[52]^=0x40u;  /* corrupt actual 96-byte receipt */
    previous=game;old=save;
    assert(tick(HM_LAB_LOAD,HM_LAB_LOAD)==HM_LORE_INVALID);
    no_change(&previous,&old);
    assert(tick(HM_LAB_RIGHT,HM_LAB_SAVE)==HM_LORE_INVALID);
    no_change(&previous,&old);
    assert(tick(UINT32_C(0x80000000),0u)==HM_LORE_INVALID);
    no_change(&previous,&old);
    assert(tick(0u,HM_LAB_WALL_UPGRADE)==HM_LORE_INVALID);
    no_change(&previous,&old);
    solids[15]^=1u;
    assert(tick(HM_LAB_RIGHT,0u)==HM_LORE_INVALID);
    no_change(&previous,&old);
    solids[15]^=1u;
    assert(tick(HM_LAB_RIGHT,0u)==HM_LORE_BLOCKED);
    assert(game.player.frame==1u);
}

static void test_jump_reset_and_debug_upgrades_are_distinct(void) {
    boot();
    assert(tick(HM_LAB_WALL_UPGRADE,HM_LAB_WALL_UPGRADE)==HM_LORE_APPLIED);
    assert(game.player.frame==0u);
    assert(tick(HM_LAB_WALL_UPGRADE,HM_LAB_WALL_UPGRADE)
           ==HM_LORE_ALREADY_DONE);
    walk(HM_LAB_RIGHT,3u);
    {
        float old_feet=game.player.feet_y;
        hm_lore_result result=tick(HM_LAB_JUMP,HM_LAB_JUMP);
        assert(result!=HM_LORE_INVALID);
        assert(game.player.feet_y<old_feet);
    }
    assert(tick(HM_LAB_RESET,HM_LAB_RESET)==HM_LORE_APPLIED);
    assert(game.player.frame==0u);
    assert(game.lore.wall_crusher_unlocked==0u);
    assert(game.attack_previous_down==0u);
}

int main(void) {
    test_source_native_lore_route_survives_save_restore();
    test_attack_held_from_spawn_requires_release_at_gate();
    test_missing_and_corrupted_restore_are_atomic();
    test_jump_reset_and_debug_upgrades_are_distinct();
    puts("PASS: Stage111 shared Switch C99 lab real movement/attack/collectibles, "
         "save-load replay, invalid receipt rollback");
    puts("Synthetic training only; no original iOS map, assets or contacts");
    return 0;
}
