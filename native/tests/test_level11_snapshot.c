/* Standalone original-Level1-1 session save contract, SYNTHETIC geometry.
 * Production hm_step is executed; NOT original iOS gameplay/save data.
 */
#include "heman_level11_snapshot.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define W 32u
#define H 12u
#define STEP (1.0f/60.0f)
static uint8_t grid[W*H];
static const hm_event events[3]={
    {HM_TRIGGER,104.0f,114.0f,4.0f},
    {HM_PICKUP,148.0f,114.0f,4.0f},
    {HM_PICKUP,56.0f,114.0f,4.0f}
};
static const hm_level11_event_bindings bindings={0u,1u,2u};
static hm_world world(void) {
    hm_world w;
    unsigned x;
    memset(&w,0,sizeof(w));memset(grid,0,sizeof(grid));
    for(x=0u;x<W;++x)grid[8u*W+x]=1u;
    w.solid=grid;w.columns=W;w.rows=H;w.tile_size=16u;
    w.spawn_x=24.0f;w.spawn_feet_y=128.0f;
    w.actor_half_width=5.0f;w.actor_height=20.0f;
    w.speed=120.0f;w.gravity=1200.0f;w.jump_speed=420.0f;
    w.terminal_speed=1400.0f;w.viewport_width=320.0f;
    w.viewport_height=192.0f;w.death_margin=96.0f;
    w.events=events;w.event_count=3u;
    return w;
}
static hm_input right(void){hm_input i={1.0f,0u,0u};return i;}
static hm_input left(void){hm_input i={-1.0f,0u,0u};return i;}
static hm_input stop(void){hm_input i={0.0f,0u,0u};return i;}
static void equal(const hm_level11_native_session *a,
                  const hm_level11_native_session *b) {
    assert(memcmp(a,b,sizeof(*a))==0);
}
static void press_or_walk(hm_level11_native_session *s,hm_input i,
                          uint8_t attack) {
    assert(hm_level11_session_step(s,i,STEP,attack)!=HM_LORE_INVALID);
}
static void make_unearned_sticky_bio(hm_level11_native_session *s) {
    unsigned n;
    /* Walk past gated reward without upgrade; core marks HM_PICKUP,
       lore must correctly leave Bio unearned. */
    for(n=0u;n<73u;++n)press_or_walk(s,right(),0u);
    assert((s->player.picked & (1u<<1))!=0u);
    assert((s->lore.collected_mask & 1u)==0u);
    assert((s->lore.collected_mask & 2u)!=0u);
    assert((s->player.triggered & 1u)!=0u);
}
static void restore_and_finish_behind_gate(void) {
    hm_world w=world();
    hm_level11_native_session a,b,saved;
    uint8_t data[HM_LEVEL11_SNAPSHOT_SIZE], other[HM_LEVEL11_SNAPSHOT_SIZE];
    unsigned n;
    assert(hm_level11_session_init(&a,&w,&bindings)==HM_LORE_APPLIED);
    make_unearned_sticky_bio(&a);
    assert(hm_level11_snapshot_encode(&a,data,sizeof(data)));
    assert(data[0]=='H' && data[1]=='1' && data[2]=='S' && data[3]=='1');
    assert(data[6]==HM_LEVEL11_SNAPSHOT_SIZE);
    memset(other,0,sizeof(other));
    assert(hm_level11_snapshot_encode(&a,other,sizeof(other)));
    assert(memcmp(data,other,sizeof(data))==0); /* canonical bytes */
    assert(hm_level11_session_init(&b,&w,&bindings)==HM_LORE_APPLIED);
    assert(hm_level11_snapshot_restore(&b,data,sizeof(data)));
    assert(memcmp(&a.player,&b.player,sizeof(a.player))==0);
    assert(memcmp(&a.lore,&b.lore,sizeof(a.lore))==0);
    assert(a.attack_previous_down==b.attack_previous_down);
    assert(b.lore.collected_count==1u);
    saved=b;
    /* Replay after save: no upgrade means no ghost reward. */
    press_or_walk(&b,stop(),1u);
    assert((b.lore.collected_mask & 1u)==0u);
    assert(hm_level11_session_grant_wall_crusher(&b,1u)==HM_LORE_APPLIED);
    press_or_walk(&b,stop(),0u);
    for(n=0u;n<31u;++n)press_or_walk(&b,left(),0u);
    assert(b.player.x<115.0f && b.player.x>96.0f);
    press_or_walk(&b,stop(),1u);
    assert(b.lore.left_gate_broken==1u);
    press_or_walk(&b,stop(),0u);
    for(n=0u;n<32u;++n)press_or_walk(&b,right(),0u);
    /* Previously seen HM_PICKUP bit is sticky, but an authentic return
       to the hidden item AFTER unlocking the gate must grant it. */
    assert(b.lore.collected_mask==3u);
    assert(b.lore.collected_count==2u);
    assert(hm_level11_snapshot_encode(&b,data,sizeof(data)));
    assert(hm_level11_snapshot_restore(&b,data,sizeof(data)));
    assert(b.lore.collected_count==2u);
    /* On a replayed save, duplicates cannot be granted again. */
    for(n=0u;n<10u;++n)press_or_walk(&b,stop(),0u);
    assert(b.lore.collected_count==2u);
    assert(saved.lore.collected_count==1u);
}
static uint64_t checksum(const uint8_t *p,size_t n) {
    uint64_t v=UINT64_C(14695981039346656037);
    size_t i;
    for(i=0;i<n;++i)v=(v^p[i])*UINT64_C(1099511628211);
    return v;
}
static void recalc(uint8_t *data) {
    uint64_t v=checksum(data,88u);
    unsigned i;
    for(i=0u;i<8u;++i)data[88u+i]=(uint8_t)(v>>(8u*i));
}
static void invalid_receipts_are_atomic(void) {
    hm_world w=world(),other=w;
    hm_level11_native_session s,copy;
    hm_level11_event_bindings swapped=bindings;
    uint8_t original[HM_LEVEL11_SNAPSHOT_SIZE],bytes[HM_LEVEL11_SNAPSHOT_SIZE];
    uint8_t dest[HM_LEVEL11_SNAPSHOT_SIZE];
    unsigned i;
    assert(hm_level11_session_init(&s,&w,&bindings)==HM_LORE_APPLIED);
    make_unearned_sticky_bio(&s);
    assert(hm_level11_snapshot_encode(&s,original,sizeof(original)));
    copy=s;
    assert(!hm_level11_snapshot_restore(&s,original,sizeof(original)-1u));
    equal(&copy,&s);
    assert(!hm_level11_snapshot_restore(&s,NULL,sizeof(original)));
    equal(&copy,&s);
    for(i=0u;i<6u;++i) {
        memcpy(bytes,original,sizeof(bytes));
        if(i==0u)bytes[0]='F';
        if(i==1u)bytes[4]=2u;  /* unknown format version */
        if(i==2u)bytes[6]=95u; /* wrong required length */
        if(i==3u)bytes[85]=1u; /* nonzero reserved byte */
        if(i==4u)bytes[64]^=1u; /* altered pickup bit */
        if(i==5u)bytes[90]^=1u; /* corrupted checksum */
        assert(!hm_level11_snapshot_restore(&s,bytes,sizeof(bytes)));
        equal(&copy,&s);
    }
    /* Recalculate checksum after forging semantic content; the format
       integrity hash is NOT a proof of logical gameplay state. */
    memcpy(bytes,original,sizeof(bytes));
    bytes[80]=2u; /* nonbinary Wall Crusher */
    recalc(bytes);
    assert(!hm_level11_snapshot_restore(&s,bytes,sizeof(bytes)));
    equal(&copy,&s);
    memcpy(bytes,original,sizeof(bytes));
    bytes[82]=3u; /* Bio falsely awarded despite gate closed */
    bytes[83]=2u;
    recalc(bytes);
    assert(!hm_level11_snapshot_restore(&s,bytes,sizeof(bytes)));
    equal(&copy,&s);
    memcpy(bytes,original,sizeof(bytes));
    bytes[76]=2u; /* invalid native grounded boolean */
    recalc(bytes);
    assert(!hm_level11_snapshot_restore(&s,bytes,sizeof(bytes)));
    equal(&copy,&s);
    memcpy(bytes,original,sizeof(bytes));
    bytes[28]=0u;bytes[29]=0u;bytes[30]=0xc0u;bytes[31]=0x7fu; /* NaN x */
    recalc(bytes);
    assert(!hm_level11_snapshot_restore(&s,bytes,sizeof(bytes)));
    equal(&copy,&s);
    memcpy(bytes,original,sizeof(bytes));
    bytes[20]=2u; /* replace Bio role with Concept Art */
    recalc(bytes);
    assert(!hm_level11_snapshot_restore(&s,bytes,sizeof(bytes)));
    equal(&copy,&s);
    memcpy(bytes,original,sizeof(bytes));
    bytes[84]=2u; /* non-binary button-latch */
    recalc(bytes);
    assert(!hm_level11_snapshot_restore(&s,bytes,sizeof(bytes)));
    equal(&copy,&s);
    /* Mismatched world geometry fails even with valid snapshot checksum. */
    other.speed+=1.0f;
    {
        hm_level11_native_session mismatch;
        assert(hm_level11_session_init(&mismatch,&other,&bindings)==HM_LORE_APPLIED);
        assert(!hm_level11_snapshot_restore(&mismatch,original,sizeof(original)));
        assert(mismatch.player.frame==0u);
    }
    swapped.skeletor_bio_event=bindings.concept_art_event;
    swapped.concept_art_event=bindings.skeletor_bio_event;
    {
        hm_level11_native_session mismatch;
        assert(hm_level11_session_init(&mismatch,&w,&swapped)==HM_LORE_APPLIED);
        assert(!hm_level11_snapshot_restore(&mismatch,original,sizeof(original)));
        assert(mismatch.player.frame==0u);
    }
    memset(dest,0xa5,sizeof(dest));
    assert(!hm_level11_snapshot_encode(&s,dest,sizeof(dest)-1u));
    for(i=0u;i<sizeof(dest);++i)assert(dest[i]==0xa5u);
    w.events=NULL;
    assert(!hm_level11_snapshot_encode(&s,dest,sizeof(dest)));
    for(i=0u;i<sizeof(dest);++i)assert(dest[i]==0xa5u);
}
int main(void) {
    restore_and_finish_behind_gate();
    invalid_receipts_are_atomic();
    puts("PASS: Stage108 canonical 96-byte native lore save/restoration,"
         " locked reward persistence and later genuine gated pickup");
    puts("No original iOS save semantics or proprietary geometry asserted");
    return 0;
}
