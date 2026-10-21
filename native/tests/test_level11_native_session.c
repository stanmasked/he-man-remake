/* Stage 105: exercise real hm_step + event adapter through a session-owned
 * rising-edge controller latch. This world is FICTIONAL, not extracted iOS.
 */
#include "heman_level11_native_session.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define CW 32u
#define CH 12u
#define DT (1.0f / 60.0f)

static uint8_t solid[CW * CH];
static const hm_event objectives[3] = {
    {HM_TRIGGER, 104.0f, 114.0f, 4.0f},
    {HM_PICKUP, 148.0f, 114.0f, 4.0f},
    {HM_PICKUP, 56.0f, 114.0f, 4.0f}
};
static const hm_level11_event_bindings roles = {0u, 1u, 2u};

static hm_world fictional_world(void) {
    hm_world w;
    unsigned x;
    memset(&w, 0, sizeof(w));
    memset(solid, 0, sizeof(solid));
    for (x=0u;x<CW;++x) solid[8u*CW+x] = 1u;
    w.solid = solid;
    w.columns=CW; w.rows=CH; w.tile_size=16u;
    w.spawn_x=24.0f; w.spawn_feet_y=128.0f;
    w.actor_half_width=5.0f; w.actor_height=20.0f;
    w.speed=120.0f; w.gravity=1200.0f; w.jump_speed=420.0f;
    w.terminal_speed=1400.0f; w.viewport_width=320.0f;
    w.viewport_height=192.0f; w.death_margin=96.0f;
    w.events=objectives; w.event_count=3u;
    return w;
}
static hm_input right(void) {
    hm_input input={1.0f, 0u, 0u};
    return input;
}
static hm_input stop(void) {
    hm_input input={0.0f, 0u, 0u};
    return input;
}
static void same(const hm_level11_native_session *a,
                 const hm_level11_native_session *b) {
    assert(memcmp(a,b,sizeof(*a))==0);
}
static void go_to_gate(hm_level11_native_session *s) {
    unsigned n;
    for(n=0u;n<100u && !(s->player.triggered & 1u);++n)
        assert(hm_level11_session_step(s,right(),DT,0u)!=HM_LORE_INVALID);
    assert(s->player.triggered & 1u);
    assert(s->player.x < 110.0f);
    assert(s->lore.collected_mask & 2u); /* freely reachable concept art */
}

static void test_button_hold_requires_real_release_at_gate(void) {
    hm_world w=fictional_world();
    hm_level11_native_session s;
    hm_lore_result r;
    unsigned n;
    assert(hm_level11_session_init(&s,&w,&roles)==HM_LORE_APPLIED);
    assert(hm_level11_session_grant_wall_crusher(&s,1u)==HM_LORE_APPLIED);
    assert(hm_level11_session_step(&s,stop(),DT,1u)==HM_LORE_BLOCKED);
    assert(s.attack_previous_down==1u);
    /* Holding A from spawn is NOT a fresh attack when later reaching gate. */
    for(n=0u;n<41u;++n)
        assert(hm_level11_session_step(&s,right(),DT,1u)!=HM_LORE_INVALID);
    assert(s.player.triggered & 1u);
    assert(s.lore.left_gate_broken==0u);
    assert(s.attack_previous_down==1u);
    assert(hm_level11_session_step(&s,stop(),DT,0u)==HM_LORE_BLOCKED);
    assert(s.attack_previous_down==0u);
    r=hm_level11_session_step(&s,stop(),DT,1u);
    assert(r==HM_LORE_APPLIED);
    assert(s.lore.left_gate_broken==1u);
    assert(hm_level11_session_step(&s,stop(),DT,1u)==HM_LORE_BLOCKED);
    assert(s.attack_previous_down==1u);
    assert(hm_level11_session_step(&s,stop(),DT,0u)==HM_LORE_BLOCKED);
    assert(hm_level11_session_step(&s,stop(),DT,1u)==HM_LORE_ALREADY_DONE);
    assert(s.lore.collected_count==1u); /* open lore already collected */
    for(n=0u;n<35u;++n)
        assert(hm_level11_session_step(&s,right(),DT,0u)!=HM_LORE_INVALID);
    assert(s.lore.collected_mask==3u);
    assert(s.lore.collected_count==2u);
}

static void test_upgrade_after_first_gate_contact(void) {
    hm_world w=fictional_world();
    hm_level11_native_session s;
    assert(hm_level11_session_init(&s,&w,&roles)==HM_LORE_APPLIED);
    go_to_gate(&s);
    assert(!s.lore.left_gate_broken);
    /* Fresh attack but no upgrade -> blocked, not latched permission. */
    assert(hm_level11_session_step(&s,stop(),DT,1u)==HM_LORE_BLOCKED);
    assert(hm_level11_session_grant_wall_crusher(&s,1u)==HM_LORE_APPLIED);
    /* Still holding attack: upgrade must NOT retroactively open gate. */
    assert(hm_level11_session_step(&s,stop(),DT,1u)==HM_LORE_BLOCKED);
    assert(s.lore.left_gate_broken==0u);
    assert(hm_level11_session_step(&s,stop(),DT,0u)==HM_LORE_BLOCKED);
    assert(hm_level11_session_step(&s,stop(),DT,1u)==HM_LORE_APPLIED);
    assert(s.lore.left_gate_broken==1u);
}

static void test_distant_attack_cannot_reuse_trigger(void) {
    hm_world w=fictional_world();
    hm_level11_native_session s;
    hm_lore_state preserved;
    unsigned n;
    assert(hm_level11_session_init(&s,&w,&roles)==HM_LORE_APPLIED);
    assert(hm_level11_session_grant_wall_crusher(&s,1u)==HM_LORE_APPLIED);
    for(n=0u;n<70u;++n)
        assert(hm_level11_session_step(&s,right(),DT,0u)!=HM_LORE_INVALID);
    assert(s.player.x>130.0f && (s.player.triggered&1u));
    preserved=s.lore;
    assert(hm_level11_session_step(&s,stop(),DT,1u)==HM_LORE_BLOCKED);
    assert(memcmp(&preserved,&s.lore,sizeof(preserved))==0);
    assert(s.lore.left_gate_broken==0u);
    assert((s.lore.collected_mask & 1u)==0u);
}

static void test_invalid_inputs_do_not_change_physics_or_latch(void) {
    hm_world w=fictional_world(), bad_world;
    hm_level11_native_session s,copy;
    hm_level11_event_bindings invalid_roles=roles;
    hm_input in=right();
    assert(hm_level11_session_init(&s,&w,&roles)==HM_LORE_APPLIED);
    copy=s;
    assert(hm_level11_session_step(&s,in,0.0f,1u)==HM_LORE_INVALID);
    same(&copy,&s);
    assert(hm_level11_session_step(&s,in,NAN,1u)==HM_LORE_INVALID);
    same(&copy,&s);
    assert(hm_level11_session_step(&s,in,DT,2u)==HM_LORE_INVALID);
    same(&copy,&s);
    in.jump=2u;
    assert(hm_level11_session_step(&s,in,DT,1u)==HM_LORE_INVALID);
    same(&copy,&s);
    in=right(); in.axis=NAN;
    assert(hm_level11_session_step(&s,in,DT,1u)==HM_LORE_INVALID);
    same(&copy,&s);
    in=right(); in.reset=2u;
    assert(hm_level11_session_step(&s,in,DT,1u)==HM_LORE_INVALID);
    same(&copy,&s);
    assert(hm_level11_session_step(NULL,right(),DT,1u)==HM_LORE_INVALID);
    assert(hm_level11_session_grant_wall_crusher(NULL,1u)==HM_LORE_INVALID);
    assert(hm_level11_session_grant_wall_crusher(&s,2u)==HM_LORE_INVALID);
    same(&copy,&s);
    invalid_roles.concept_art_event=invalid_roles.skeletor_bio_event;
    assert(!hm_level11_native_bindings_valid(&w,&invalid_roles));
    assert(hm_level11_session_init(&s,&w,&invalid_roles)==HM_LORE_INVALID);
    same(&copy,&s);
    bad_world=w;
    bad_world.events=NULL;
    assert(hm_level11_session_init(&s,&bad_world,&roles)==HM_LORE_INVALID);
    same(&copy,&s);
    s.bindings.left_gate_event=1u; /* corrupt runtime binding */
    copy=s;
    assert(hm_level11_session_step(&s,right(),DT,1u)==HM_LORE_INVALID);
    same(&copy,&s);
}

static void test_reset_does_not_grant_an_attack_or_lore(void) {
    hm_world w=fictional_world();
    hm_level11_native_session s;
    hm_input reset=stop();
    hm_lore_state saved;
    assert(hm_level11_session_init(&s,&w,&roles)==HM_LORE_APPLIED);
    assert(hm_level11_session_grant_wall_crusher(&s,1u)==HM_LORE_APPLIED);
    go_to_gate(&s);
    saved=s.lore;
    reset.reset=1u;
    assert(hm_level11_session_step(&s,reset,DT,1u)==HM_LORE_BLOCKED);
    assert(s.player.respawns==1u);
    assert(s.attack_previous_down==1u);
    assert(memcmp(&saved,&s.lore,sizeof(saved))==0);
    /* Holding the same button on the walk back cannot mint a fresh hit. */
    {
        unsigned n;
        for(n=0u;n<41u;++n)
            assert(hm_level11_session_step(&s,right(),DT,1u)!=HM_LORE_INVALID);
    }
    assert(s.lore.left_gate_broken==0u);
}
static void test_original_fixture_content_is_sealed_without_export(void) {
    hm_world w=fictional_world();
    hm_event mutable_events[3];
    hm_level11_native_session s, saved;
    uint8_t old_tile;
    float old_speed;
    memcpy(mutable_events, objectives, sizeof(mutable_events));
    w.events=mutable_events;
    assert(hm_level11_session_init(&s,&w,&roles)==HM_LORE_APPLIED);
    saved=s;

    /* Valid event type and identity, but different geometry: reject before
       the hero can collect either lore token at a new invented position. */
    mutable_events[2].x += 6.0f;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    assert(hm_level11_session_grant_wall_crusher(&s,1u)==HM_LORE_INVALID);
    same(&saved,&s);
    mutable_events[2].x -= 6.0f;

    /* Changes to even non-lore spatial fixtures are detected. */
    mutable_events[0].radius += 1.0f;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    mutable_events[0].radius -= 1.0f;

    /* Mutable borrowed collision data, even with an identical pointer. */
    old_tile=solid[CW+1u];
    solid[CW+1u]=(uint8_t)(old_tile ? 0u : 1u);
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    solid[CW+1u]=old_tile;

    /* A physics edit is not a valid continuation of a sealed session. */
    old_speed=w.speed; w.speed+=1.0f;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    w.speed=old_speed;

    /* Pointer replacement with semantically identical fixtures is still
       forbidden: callers must not swap a borrowed map under a session. */
    w.events=objectives;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    w.events=mutable_events;

    /* Original size limits retained, even if the caller corrupts header. */
    w.columns=4096u;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    w.columns=CW;
    w.event_count=32u;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    w.event_count=3u;

    /* Restore data, then allow normal engine movement and only genuine
       world events. No sticky permanent failure on a private rollback. */
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_BLOCKED);
    assert(s.player.frame==1u);
    assert(s.world_seal==saved.world_seal);
}

static void test_masked_grid_mutations_are_rejected_without_overread(void) {
    hm_world w=fictional_world();
    hm_mask_grid grid;
    uint16_t tile_ids[CW*CH], alternative_ids[CW*CH];
    uint64_t rows[16];
    hm_level11_native_session s, saved;
    uint32_t i;
    for(i=0u;i<CW*CH;++i)
        tile_ids[i]=(uint16_t)((i/CW)==8u ? 0u : UINT16_MAX);
    for(i=0u;i<16u;++i) rows[i]=UINT64_C(0xffff);
    memset(&grid,0,sizeof(grid));
    grid.tile_ids=tile_ids; grid.mask_rows=rows;
    grid.columns=CW; grid.rows=CH; grid.tile_size=16u;
    grid.mask_count=1u;
    w.solid=NULL;
    w.mask_grid=&grid;
    assert(hm_mask_valid(&grid));
    assert(hm_level11_session_init(&s,&w,&roles)==HM_LORE_APPLIED);
    saved=s;

    rows[0]^=UINT64_C(1);
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    rows[0]^=UINT64_C(1);

    tile_ids[0]=0u;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    tile_ids[0]=UINT16_MAX;

    /* Reject changed metadata and avoid scanning beyond saved allocations. */
    grid.mask_count=1024u;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    grid.mask_count=1u;
    grid.columns=4096u;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    grid.columns=CW;

    memcpy(alternative_ids,tile_ids,sizeof(alternative_ids));
    grid.tile_ids=alternative_ids;
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_INVALID);
    same(&saved,&s);
    grid.tile_ids=tile_ids;

    /* A restored mask resource permits the next actual native step. */
    assert(hm_level11_session_step(&s,right(),DT,0u)==HM_LORE_BLOCKED);
    assert(s.player.frame==1u);
}

static void test_corrupt_world_is_not_allowed_on_new_init(void) {
    hm_world w=fictional_world(), corrupted;
    hm_level11_native_session s,saved;
    assert(hm_level11_session_init(&s,&w,&roles)==HM_LORE_APPLIED);
    saved=s;
    corrupted=w;
    corrupted.columns=4097u; /* invalid core size without reading tiles */
    assert(hm_level11_session_init(&s,&corrupted,&roles)==HM_LORE_INVALID);
    same(&saved,&s);
}

int main(void) {
    test_button_hold_requires_real_release_at_gate();
    test_upgrade_after_first_gate_contact();
    test_distant_attack_cannot_reuse_trigger();
    test_invalid_inputs_do_not_change_physics_or_latch();
    test_reset_does_not_grant_an_attack_or_lore();
    test_original_fixture_content_is_sealed_without_export();
    test_masked_grid_mutations_are_rejected_without_overread();
    test_corrupt_world_is_not_allowed_on_new_init();
    puts("PASS: Stage106 immutable borrowed native world seal prevents altered "
         "event map, solid tiles, mask geometry and physics replay");
    puts("PASS: Stage105 source-native session derives fresh attack on 0->1,"
         " never from held A; only real hm_step gate overlap grants lore");
    puts("Synthetic event geometry only; genuine iOS inputs/assets unverified");
    return 0;
}
