#include "heman_level11_journal.h"
#include <limits.h>
#include <string.h>

#define RECORD_SIZE HM_LEVEL11_JOURNAL_RECORD_SIZE
#define DATA_OFFSET 16u
#define HASH_OFFSET 112u

static void put64(uint8_t *p, uint64_t value) {
    unsigned i;
    for (i=0u; i<8u; ++i) p[i]=(uint8_t)(value >> (8u*i));
}
static uint64_t get64(const uint8_t *p) {
    uint64_t result=0u;
    unsigned i;
    for (i=0u; i<8u; ++i) result |= ((uint64_t)p[i]) << (8u*i);
    return result;
}
static uint64_t fnv64(const uint8_t *bytes, unsigned n) {
    uint64_t hash=UINT64_C(14695981039346656037);
    unsigned i;
    for (i=0u; i<n; ++i)
        hash=(hash^(uint64_t)bytes[i])*UINT64_C(1099511628211);
    return hash;
}
static int valid_outer(const uint8_t data[RECORD_SIZE]) {
    if (memcmp(data,"H1J1",4u)!=0 || data[4]!=1u ||
        data[5]!=0u || data[6]!=0u || data[7]!=0u ||
        get64(data+8u)==0u ||
        get64(data+HASH_OFFSET)!=fnv64(data,HASH_OFFSET))
        return 0;
    return 1;
}
static int io_valid(const hm_level11_journal_io *io) {
    return io && io->read_slot && io->write_slot;
}
/* Never mutate source. Every purported disk record is checked against a
 * independently valid native world/session before being trusted.
 */
static int read_compatible(const hm_level11_journal_io *io, unsigned slot,
                           const hm_level11_native_session *source,
                           uint64_t *generation,
                           hm_level11_native_session *candidate) {
    uint8_t bytes[RECORD_SIZE];
    if (io->read_slot(io->context,slot,bytes)!=1 ||
        !valid_outer(bytes)) return 0;
    *candidate=*source;
    if (!hm_level11_snapshot_restore(candidate,bytes+DATA_OFFSET,
                                      HM_LEVEL11_SNAPSHOT_SIZE))
        return 0;
    *generation=get64(bytes+8u);
    return 1;
}

int hm_level11_journal_restore(hm_level11_native_session *session,
                               const hm_level11_journal_io *io,
                               uint64_t *generation) {
    hm_level11_native_session candidates[2];
    uint64_t ages[2]={0u,0u};
    int good[2],chosen;
    if (!session || !io_valid(io) || !hm_level11_session_valid(session))
        return 0;
    good[0]=read_compatible(io,0u,session,&ages[0],&candidates[0]);
    good[1]=read_compatible(io,1u,session,&ages[1],&candidates[1]);
    if (!good[0] && !good[1]) return 0;
    chosen=good[1] && (!good[0] || ages[1]>ages[0]) ? 1 : 0;
    *session=candidates[chosen]; /* one commit; source world retained */
    if (generation) *generation=ages[chosen];
    return 1;
}

int hm_level11_journal_store(const hm_level11_native_session *session,
                             const hm_level11_journal_io *io,
                             uint64_t *generation) {
    uint8_t bytes[RECORD_SIZE];
    hm_level11_native_session candidate;
    uint64_t ages[2]={0u,0u},last=0u;
    int good[2];
    unsigned slot;
    if (!session || !io_valid(io) || !hm_level11_session_valid(session))
        return 0;
    memset(bytes,0,sizeof(bytes));
    if (!hm_level11_snapshot_encode(session,bytes+DATA_OFFSET,
                                    HM_LEVEL11_SNAPSHOT_SIZE))
        return 0;
    good[0]=read_compatible(io,0u,session,&ages[0],&candidate);
    good[1]=read_compatible(io,1u,session,&ages[1],&candidate);
    if (good[0] && (!good[1] || ages[0]>=ages[1])) {
        slot=1u; last=ages[0];
    } else if (good[1]) {
        slot=0u; last=ages[1];
    } else {
        slot=0u;
    }
    if (last==UINT64_MAX) return 0; /* no ambiguous wraparound ordering */
    memcpy(bytes,"H1J1",4u); bytes[4]=1u;
    put64(bytes+8u,last+1u);
    put64(bytes+HASH_OFFSET,fnv64(bytes,HASH_OFFSET));
    /* Writes exclusively into older/invalid slot. A failed or torn
     * write cannot erase the previously valid slot through this API.
     * A platform must never implement callbacks that overwrite both. */
    if (io->write_slot(io->context,slot,bytes)!=1)
        return 0;
    /* A callback reporting success is not sufficient evidence that the
     * bytes on disk are intact. Read back the target and validate its
     * envelope, snapshot/world binding and expected generation before
     * telling the caller the save committed. The prior good slot is still
     * untouched if this verification fails. */
    {
        uint64_t verified_generation=0u;
        if (!read_compatible(io,slot,session,&verified_generation,&candidate) ||
            verified_generation!=last+1u)
            return 0;
    }
    if (generation) *generation=last+1u;
    return 1;
}
