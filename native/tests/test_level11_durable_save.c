/* Synthetic C99 Switch-lore save durability tests. No original IPA data.
 * POSIX temp fixtures only for Linux native CI; production module is C99.
 */
#define _POSIX_C_SOURCE 200809L
#include "heman_level11_durable_save.h"
#include "heman_level11_lab.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static hm_world world;
static uint8_t solid[HM_LORE_LAB_CELLS];
static hm_level11_native_session session;
static char folder[]="/tmp/heman-durable-XXXXXX";
static char prefix[320];
static char files[2][340];

static void init(void) {
    assert(hm_level11_lab_init(&world,solid,sizeof(solid),&session)
            ==HM_LORE_APPLIED);
}
static void move_right(unsigned n) {
    unsigned k;
    for(k=0u;k<n;++k)
        assert(hm_level11_lab_tick(&session,NULL,0u,0u)==HM_LORE_INVALID);
}
static void advance(unsigned n) {
    unsigned k;
    hm_level11_lab_save ram={{0},0};
    for(k=0u;k<n;++k)
        assert(hm_level11_lab_tick(&session,&ram,HM_LAB_RIGHT,0u)
               !=HM_LORE_INVALID);
}
static void state_unchanged(const hm_level11_native_session *before) {
    assert(memcmp(&session,before,sizeof(session))==0);
}
static void make_filename(unsigned n) {
    assert(snprintf(files[n],sizeof(files[n]),"%s.%u.bin",prefix,n)>0);
}
static void write_bytes(unsigned slot,size_t bytes,uint8_t value) {
    FILE *f=fopen(files[slot],"wb");
    size_t k;
    assert(f);
    for(k=0u;k<bytes;++k)assert(fputc(value,f)!=EOF);
    assert(fclose(f)==0);
}
static void mutate_byte(unsigned slot,long offset) {
    FILE *f=fopen(files[slot],"r+b");
    int c;
    assert(f && fseek(f,offset,SEEK_SET)==0);
    c=fgetc(f);
    assert(c!=EOF);
    assert(fseek(f,offset,SEEK_SET)==0);
    assert(fputc(c^0x5a,f)!=EOF);
    assert(fclose(f)==0);
}
static void test_cold_reinit_and_second_slot(void) {
    hm_level11_native_session captured;
    init();
    assert(hm_level11_durable_load(prefix,&session)==HM_DURABLE_EMPTY);
    advance(73u);
    captured=session;
    assert(session.lore.collected_count==1u);
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    assert(access(files[0],F_OK)==0);
    assert(access(files[1],F_OK)!=0);
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    assert(access(files[1],F_OK)==0);
    init(); /* new world and session, same address and native fixture */
    assert(session.player.frame==0u);
    assert(hm_level11_durable_load(prefix,&session)==HM_DURABLE_OK);
    assert(memcmp(&session.player,&captured.player,
                  sizeof(session.player))==0);
    assert(memcmp(&session.lore,&captured.lore,
                  sizeof(session.lore))==0);
    assert(session.attack_previous_down==captured.attack_previous_down);
}
static void test_latest_corrupt_recovers_previous(void) {
    hm_level11_native_session older;
    init();
    advance(16u);
    older=session;
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    advance(7u);
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    /* latest: slot1, older remains untouched in slot0 */
    mutate_byte(1u,27);
    init();
    assert(hm_level11_durable_load(prefix,&session)==HM_DURABLE_OK);
    assert(memcmp(&session.player,&older.player,
                  sizeof(session.player))==0);
    assert(memcmp(&session.lore,&older.lore,sizeof(session.lore))==0);
    /* replacement write must use damaged slot, preserve sound older */
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    assert(hm_level11_durable_load(prefix,&session)==HM_DURABLE_OK);
}
static void test_torn_overflow_and_invalid_state(void) {
    hm_level11_native_session before;
    init();
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    write_bytes(0u,15u,0x44u);
    write_bytes(1u,2u,0x33u);
    before=session;
    assert(hm_level11_durable_load(prefix,&session)==HM_DURABLE_CORRUPT);
    state_unchanged(&before);
    /* A new good snapshot can replace a damaged slot. */
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    assert(hm_level11_durable_load(prefix,&session)==HM_DURABLE_OK);
    before=session;
    assert(hm_level11_durable_store("/a/path/not/present/stage113",&session)
            ==HM_DURABLE_IO_ERROR);
    state_unchanged(&before);
    session.lore.collected_count=3u; /* fake impossible bonus */
    before=session;
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_INCOMPATIBLE);
    state_unchanged(&before);
}
static void test_world_mismatch_and_failure_atomic(void) {
    hm_world incompatible_world;
    hm_level11_native_session incompatible,unchanged;
    init();
    advance(20u);
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    incompatible_world=world;
    incompatible_world.speed+=4.0f;
    assert(hm_level11_session_init(&incompatible,&incompatible_world,
            &session.sealed_bindings)==HM_LORE_APPLIED);
    unchanged=incompatible;
    assert(hm_level11_durable_load(prefix,&incompatible)
            ==HM_DURABLE_INCOMPATIBLE);
    assert(memcmp(&incompatible,&unchanged,sizeof(incompatible))==0);
    assert(hm_level11_durable_store(prefix,&incompatible)
            ==HM_DURABLE_INCOMPATIBLE);
    assert(memcmp(&incompatible,&unchanged,sizeof(incompatible))==0);
}
static void test_file_overlength_rejected(void) {
    hm_level11_native_session before;
    init();
    write_bytes(0u,129u,0x11u);
    write_bytes(1u,129u,0x22u);
    before=session;
    assert(hm_level11_durable_load(prefix,&session)==HM_DURABLE_CORRUPT);
    state_unchanged(&before);
    assert(hm_level11_durable_store(prefix,&session)==HM_DURABLE_OK);
    assert(hm_level11_durable_load(prefix,&session)==HM_DURABLE_OK);
}
int main(void) {
    assert(mkdtemp(folder)!=NULL);
    assert(snprintf(prefix,sizeof(prefix),"%s/lore-lab",folder)>0);
    make_filename(0u);make_filename(1u);
    test_cold_reinit_and_second_slot();
    assert(remove(files[0])==0 && remove(files[1])==0);
    test_latest_corrupt_recovers_previous();
    assert(remove(files[0])==0 && remove(files[1])==0);
    test_torn_overflow_and_invalid_state();
    assert(remove(files[0])==0);
    if(access(files[1],F_OK)==0)assert(remove(files[1])==0);
    test_world_mismatch_and_failure_atomic();
    assert(remove(files[0])==0);
    if(access(files[1],F_OK)==0)assert(remove(files[1])==0);
    test_file_overlength_rejected();
    assert(remove(files[0])==0);
    if(access(files[1],F_OK)==0)assert(remove(files[1])==0);
    assert(rmdir(folder)==0);
    puts("PASS: Stage113 real C99 two-slot filesystem save, fresh-session "
         "load, sequence, torn-write fallback, malformed/foreign rejection");
    puts("Fictional test world and owned save format; no real iOS persistence.");
    return 0;
}
