#include "heman_level11_journal.h"
#include "heman_level11_lab.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SZ HM_LEVEL11_JOURNAL_RECORD_SIZE
typedef struct {
    uint8_t bytes[2][SZ];
    int exists[2];
    unsigned writes;
    int tear_next;
} memory_slots;
static uint8_t solids[HM_LORE_LAB_CELLS];
static hm_world world;
static hm_level11_native_session game;

static int memory_read(void *ctx,unsigned slot,uint8_t *data) {
    memory_slots *s=(memory_slots*)ctx;
    if (slot>1u || !s->exists[slot]) return 0;
    memcpy(data,s->bytes[slot],SZ);
    return 1;
}
static int memory_write(void *ctx,unsigned slot,const uint8_t *data) {
    memory_slots *s=(memory_slots*)ctx;
    if(slot>1u)return 0;
    s->writes++;
    if(s->tear_next) {
        s->tear_next=0;
        memcpy(s->bytes[slot],data,SZ/2u);
        s->exists[slot]=1;
        return 0;
    }
    memcpy(s->bytes[slot],data,SZ);
    s->exists[slot]=1;
    return 1;
}
static void boot(void) {
    assert(hm_level11_lab_init(&world,solids,sizeof(solids),&game)
           ==HM_LORE_APPLIED);
}
static void walk(unsigned n) {
    unsigned i;
    hm_input right={1.0f,0u,0u};
    for(i=0u;i<n;++i)
        assert(hm_level11_session_step(&game,right,1.0f/60.0f,0u)
                !=HM_LORE_INVALID);
}
static void put64(uint8_t *p,uint64_t v) {
    unsigned i;
    for(i=0u;i<8u;++i)p[i]=(uint8_t)(v>>(8u*i));
}
static uint64_t fnv(const uint8_t *p,unsigned n) {
    uint64_t x=UINT64_C(14695981039346656037);
    unsigned i;
    for(i=0u;i<n;++i)x=(x^p[i])*UINT64_C(1099511628211);
    return x;
}
static void memory_tests(void) {
    memory_slots m;
    hm_level11_journal_io io;
    uint64_t generation=777u;
    hm_level11_native_session before;
    hm_world otherworld;
    hm_level11_native_session foreign;
    const hm_level11_event_bindings roles={0u,1u,2u};
    memset(&m,0,sizeof(m));
    io.context=&m;io.read_slot=memory_read;io.write_slot=memory_write;
    boot();
    before=game;
    assert(!hm_level11_journal_restore(&game,&io,&generation));
    assert(generation==777u && memcmp(&before,&game,sizeof(game))==0);
    walk(30u);
    assert(game.lore.collected_mask==2u);
    assert(hm_level11_journal_store(&game,&io,&generation));
    assert(generation==1u && m.exists[0] && !m.exists[1]);
    assert(hm_level11_session_grant_wall_crusher(&game,1u)==HM_LORE_APPLIED);
    assert(hm_level11_journal_store(&game,&io,&generation));
    assert(generation==2u && m.exists[0] && m.exists[1]);
    boot();
    assert(hm_level11_journal_restore(&game,&io,&generation));
    assert(generation==2u && game.lore.wall_crusher_unlocked==1u);
    assert(game.lore.collected_mask==2u);
    /* Lose the most recent complete save. Restore old good generation1. */
    m.bytes[1][24u]^=0x40u;
    boot();
    assert(hm_level11_journal_restore(&game,&io,&generation));
    assert(generation==1u && game.lore.wall_crusher_unlocked==0u);
    assert(m.bytes[0][0u]=='H' && m.bytes[0][1u]=='1');
    /* Torn third commit must NOT erase generation1. */
    m.tear_next=1;
    assert(!hm_level11_journal_store(&game,&io,&generation));
    boot();
    assert(hm_level11_journal_restore(&game,&io,&generation));
    assert(generation==1u && game.lore.collected_mask==2u);
    /* The second attempt repairs the damaged candidate, never invalidating
     * the first existing good journal slot. */
    assert(hm_level11_session_grant_wall_crusher(&game,1u)==HM_LORE_APPLIED);
    assert(hm_level11_journal_store(&game,&io,&generation));
    assert(generation==2u);
    /* Unsupported schema+checksum, a torn slot, and a non-authentic
     * original world seal must each fail closed or use valid fallback. */
    m.bytes[1][4u]=2u;
    boot();
    assert(hm_level11_journal_restore(&game,&io,&generation));
    assert(generation==1u && game.lore.wall_crusher_unlocked==0u);
    m.bytes[1][4u]=1u;
    otherworld=world;
    otherworld.speed+=1.0f;
    assert(hm_level11_session_init(&foreign,&otherworld,&roles)
           ==HM_LORE_APPLIED);
    before=foreign;
    assert(!hm_level11_journal_restore(&foreign,&io,&generation));
    assert(memcmp(&before,&foreign,sizeof(foreign))==0);
    /* Simulate an unwrapped maximum generation: no new file is allowed. */
    put64(m.bytes[0]+8u,UINT64_MAX);
    put64(m.bytes[0]+112u,fnv(m.bytes[0],112u));
    m.exists[1]=0;
    {
        unsigned writes=m.writes;
        assert(!hm_level11_journal_store(&game,&io,&generation));
        assert(m.writes==writes);
    }
    /* API rejects partial IO capabilities without mutating live session. */
    io.write_slot=NULL;
    before=game;
    assert(!hm_level11_journal_store(&game,&io,&generation));
    assert(!hm_level11_journal_restore(&game,&io,&generation));
    assert(memcmp(&before,&game,sizeof(game))==0);
}
typedef struct {char prefix[256];} files;
static int file_name(const files *p,unsigned slot,char *out,size_t n) {
    int r;
    if(slot>1u)return 0;
    r=snprintf(out,n,"%s.%u",p->prefix,slot);
    return r>0 && (size_t)r<n;
}
static int file_read(void *ctx,unsigned slot,uint8_t *data) {
    files *p=(files*)ctx;
    char path[300];
    FILE *fp;
    size_t amount;
    int extra,closed;
    if(!file_name(p,slot,path,sizeof(path)))return 0;
    fp=fopen(path,"rb");if(!fp)return 0;
    amount=fread(data,1u,SZ,fp);
    extra=fgetc(fp);
    closed=fclose(fp);
    return amount==SZ && extra==EOF && closed==0;
}
static int file_write(void *ctx,unsigned slot,const uint8_t *data) {
    files *p=(files*)ctx;
    char path[300];
    FILE *fp;
    size_t amount;
    int flushed,closed;
    if(!file_name(p,slot,path,sizeof(path)))return 0;
    fp=fopen(path,"wb");if(!fp)return 0;
    amount=fwrite(data,1u,SZ,fp);
    flushed=fflush(fp);closed=fclose(fp);
    return amount==SZ && flushed==0 && closed==0;
}
static void cold_process(const char *mode,const char *path) {
    files p;
    hm_level11_journal_io io;
    uint64_t generation=0u;
    assert(strlen(path)<sizeof(p.prefix));
    memset(&p,0,sizeof(p));strcpy(p.prefix,path);
    io.context=&p;io.read_slot=file_read;io.write_slot=file_write;
    boot();
    if(strcmp(mode,"cold-write")==0) {
        walk(30u);
        assert(hm_level11_journal_store(&game,&io,&generation));
        assert(generation==1u);
    } else if(strcmp(mode,"cold-read")==0) {
        assert(hm_level11_journal_restore(&game,&io,&generation));
        assert(generation==1u);
        assert(game.lore.collected_mask==2u);
        assert(game.lore.wall_crusher_unlocked==0u);
        assert(game.player.frame==30u);
    } else if(strcmp(mode,"cold-upgrade")==0) {
        assert(hm_level11_journal_restore(&game,&io,&generation));
        assert(generation==1u);
        assert(hm_level11_session_grant_wall_crusher(&game,1u)
               ==HM_LORE_APPLIED);
        assert(hm_level11_journal_store(&game,&io,&generation));
        assert(generation==2u);
    } else if(strcmp(mode,"cold-read-upgrade")==0) {
        assert(hm_level11_journal_restore(&game,&io,&generation));
        assert(generation==2u);
        assert(game.lore.wall_crusher_unlocked==1u);
        assert(game.lore.collected_mask==2u);
    } else {
        assert(!"unknown cold process command");
    }
    printf("PASS: Stage113 %s (separate process)\n",mode);
}
int main(int argc,char **argv) {
    if(argc==3) {
        cold_process(argv[1],argv[2]);
    } else {
        assert(argc==1);
        memory_tests();
        puts("PASS: Stage113 two-slot rollback, incompatible world rejection, "
             "torn write, broken digest, monotonic generation and no live mutation");
    }
    return 0;
}
