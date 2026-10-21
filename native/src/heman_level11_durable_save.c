#include "heman_level11_durable_save.h"
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define SLOT_BYTES HM_LEVEL11_DURABLE_SLOT_SIZE
#define PATH_BYTES 384u

typedef struct {
    uint8_t bytes[SLOT_BYTES];
    uint64_t sequence;
    int status; /* 1 valid, 0 absent, -1 I/O error, -2 damaged */
} durable_slot;

static void put64(uint8_t *p, uint64_t value) {
    unsigned i;
    for (i=0u;i<8u;++i) p[i]=(uint8_t)(value>>(8u*i));
}
static uint64_t get64(const uint8_t *p) {
    unsigned i;
    uint64_t value=0;
    for (i=0u;i<8u;++i) value |= ((uint64_t)p[i])<<(8u*i);
    return value;
}
static uint64_t checksum(const uint8_t *p,size_t n) {
    uint64_t value=UINT64_C(14695981039346656037);
    size_t i;
    for (i=0u;i<n;++i)
        value=(value^(uint64_t)p[i])*UINT64_C(1099511628211);
    return value;
}
static int slot_path(char path[PATH_BYTES], const char *prefix,unsigned index) {
    int n;
    if (!prefix || !*prefix || index>1u ||
        strlen(prefix)>PATH_BYTES-16u) return 0;
    n=snprintf(path,PATH_BYTES,"%s.%u.bin",prefix,index);
    return n>0 && (size_t)n<PATH_BYTES;
}
static int decode(durable_slot *slot) {
    const uint8_t *data=slot->bytes;
    unsigned i;
    if (memcmp(data,"HLD1",4u)!=0 ||
        data[4]!=1u || data[5]!=0u || data[6]!=0u || data[7]!=0u ||
        get64(data+112u)!=checksum(data,112u))
        return 0;
    for(i=120u;i<SLOT_BYTES;++i)
        if(data[i]!=0u) return 0;
    slot->sequence=get64(data+8u);
    return slot->sequence!=0u;
}
static void read_slot(const char *prefix,unsigned index,durable_slot *out) {
    char path[PATH_BYTES];
    FILE *file;
    size_t n;
    int extra, err;
    memset(out,0,sizeof(*out));
    if (!slot_path(path,prefix,index)) {out->status=-1;return;}
    file=fopen(path,"rb");
    if (!file) {
        out->status=(errno==ENOENT)?0:-1;
        return;
    }
    n=fread(out->bytes,1u,SLOT_BYTES,file);
    extra=fgetc(file);
    err=ferror(file);
    if(fclose(file)!=0) err=1;
    if(err) {out->status=-1;return;}
    if(n!=SLOT_BYTES || extra!=EOF || !decode(out)) {
        out->status=-2;
        return;
    }
    out->status=1;
}
static int compatible(const hm_level11_native_session *session,
                      const durable_slot *s) {
    hm_level11_native_session probe=*session;
    return hm_level11_snapshot_restore(&probe,
                s->bytes+16u,HM_LEVEL11_SNAPSHOT_SIZE);
}
static int failure(const durable_slot *a,const durable_slot *b,int incompat) {
    if (a->status==-1 || b->status==-1) return HM_DURABLE_IO_ERROR;
    if (incompat) return HM_DURABLE_INCOMPATIBLE;
    if (a->status==-2 || b->status==-2) return HM_DURABLE_CORRUPT;
    return HM_DURABLE_EMPTY;
}
int hm_level11_durable_load(const char *prefix,
                            hm_level11_native_session *session) {
    durable_slot slots[2];
    hm_level11_native_session next;
    int best=-1,incompat=0;
    unsigned i;
    uint64_t max_sequence=0u;
    if (!prefix || !session || !hm_level11_session_valid(session))
        return HM_DURABLE_INCOMPATIBLE;
    read_slot(prefix,0u,&slots[0]);read_slot(prefix,1u,&slots[1]);
    for(i=0u;i<2u;++i) {
        if (slots[i].status!=1) continue;
        if (!compatible(session,&slots[i])) {incompat=1;continue;}
        if (best<0 || slots[i].sequence>max_sequence) {
            best=(int)i;
            max_sequence=slots[i].sequence;
        }
    }
    if(best<0) return failure(&slots[0],&slots[1],incompat);
    next=*session;
    if(!hm_level11_snapshot_restore(&next,slots[best].bytes+16u,
                                    HM_LEVEL11_SNAPSHOT_SIZE))
        return HM_DURABLE_INCOMPATIBLE;
    *session=next;
    return HM_DURABLE_OK;
}
int hm_level11_durable_store(const char *prefix,
                             const hm_level11_native_session *session) {
    durable_slot slots[2];
    uint8_t bytes[SLOT_BYTES];
    uint64_t top=0u;
    unsigned target=0u,i;
    char path[PATH_BYTES];
    FILE *file;
    size_t count;
    int failed;
    if (!prefix || !session || !slot_path(path,prefix,0u) ||
        !hm_level11_snapshot_encode(session,bytes+16u,
                                   HM_LEVEL11_SNAPSHOT_SIZE))
        return HM_DURABLE_INCOMPATIBLE;
    read_slot(prefix,0u,&slots[0]);read_slot(prefix,1u,&slots[1]);
    for(i=0u;i<2u;++i) {
        if(slots[i].status==-1) return HM_DURABLE_IO_ERROR;
        if(slots[i].status!=1) continue;
        if(!compatible(session,&slots[i]))
            return HM_DURABLE_INCOMPATIBLE;
        if(slots[i].sequence>top) top=slots[i].sequence;
    }
    if(top==UINT64_MAX) return HM_DURABLE_INCOMPATIBLE;
    if(slots[0].status==1 && slots[1].status==1) {
        target=(slots[0].sequence<=slots[1].sequence)?0u:1u;
    } else if(slots[0].status==1) {
        target=1u;
    } else if(slots[1].status==1) {
        target=0u;
    }
    if(!slot_path(path,prefix,target)) return HM_DURABLE_IO_ERROR;
    /* First 16 bytes of record; bytes 16..111 already contain canonical
     * source-native 96-byte receipt. Two slots preserve previous file
     * during the next attempted write. */
    memcpy(bytes,"HLD1",4u);
    memset(bytes+4u,0,12u);
    bytes[4]=1u;
    put64(bytes+8u,top+UINT64_C(1));
    put64(bytes+112u,checksum(bytes,112u));
    memset(bytes+120u,0,SLOT_BYTES-120u);
    file=fopen(path,"wb");
    if(!file) return HM_DURABLE_IO_ERROR;
    count=fwrite(bytes,1u,sizeof(bytes),file);
    failed=(count!=sizeof(bytes) || fflush(file)!=0);
    if(fclose(file)!=0) failed=1;
    return failed?HM_DURABLE_IO_ERROR:HM_DURABLE_OK;
}
