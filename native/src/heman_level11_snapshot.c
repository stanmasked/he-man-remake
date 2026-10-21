#include "heman_level11_snapshot.h"
#include <limits.h>
#include <math.h>
#include <string.h>

/* Canonical 96-byte in-memory receipt; no pointers, padding or native
 * struct layouts are serialized. Only a private experimental save format.
 * Bytes 0..87 are covered by the non-cryptographic checksum at 88..95. */
static void put16(uint8_t *p, uint16_t v) {
    p[0]=(uint8_t)v; p[1]=(uint8_t)(v >> 8);
}
static void put32(uint8_t *p, uint32_t v) {
    unsigned n;
    for(n=0u;n<4u;++n) p[n]=(uint8_t)(v >> (8u*n));
}
static void put64(uint8_t *p, uint64_t v) {
    unsigned n;
    for(n=0u;n<8u;++n) p[n]=(uint8_t)(v >> (8u*n));
}
static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
           ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static uint64_t get64(const uint8_t *p) {
    uint64_t v=0u;
    unsigned n;
    for(n=0u;n<8u;++n) v|=((uint64_t)p[n]) << (8u*n);
    return v;
}
static uint64_t checksum(const uint8_t *data, size_t size) {
    uint64_t value=UINT64_C(14695981039346656037);
    size_t i;
    for(i=0u;i<size;++i)
        value=(value ^ (uint64_t)data[i])*UINT64_C(1099511628211);
    return value;
}
static void put_float(uint8_t *p, float v) {
    uint32_t bits=0;
    memcpy(&bits,&v,sizeof(bits));
    put32(p,bits);
}
static float get_float(const uint8_t *p) {
    uint32_t bits=get32(p);
    float v=0.0f;
    memcpy(&v,&bits,sizeof(v));
    return v;
}
static int state_plausible(const hm_level11_native_session *session) {
    const hm_state *s=&session->player;
    const hm_lore_state *l=&session->lore;
    const hm_world *w=session->world;
    uint32_t allowed, i;
    if (!isfinite(s->x) || !isfinite(s->feet_y) ||
        !isfinite(s->vy) || !isfinite(s->camera_x) ||
        !isfinite(s->camera_y) ||
        fabsf(s->x)>1000000.0f || fabsf(s->feet_y)>1000000.0f ||
        fabsf(s->vy)>1000000.0f ||
        fabsf(s->camera_x)>1000000.0f ||
        fabsf(s->camera_y)>1000000.0f ||
        s->grounded>1u || s->wall_hit>1u ||
        s->ceiling_hit>1u || s->completed>1u ||
        s->checkpoint < -1 || s->checkpoint >= (int32_t)w->event_count ||
        s->frame == UINT32_MAX || s->respawns == UINT32_MAX ||
        s->landings == UINT32_MAX || s->hazards == UINT32_MAX)
        return 0;
    if (s->checkpoint >= 0 &&
        w->events[s->checkpoint].kind != HM_CHECKPOINT) return 0;
    allowed=w->event_count==32u ? UINT32_MAX :
            (UINT32_C(1) << w->event_count)-UINT32_C(1);
    if ((s->picked & ~allowed) || (s->triggered & ~allowed))
        return 0;
    for(i=0u;i<w->event_count;++i) {
        const uint32_t bit=UINT32_C(1)<<i;
        if ((s->picked & bit) && w->events[i].kind!=HM_PICKUP) return 0;
        if ((s->triggered & bit) && w->events[i].kind!=HM_TRIGGER) return 0;
    }
    if ((l->collected_mask & 1u) &&
        !(s->picked & (UINT32_C(1)<<session->bindings.skeletor_bio_event)))
        return 0;
    if ((l->collected_mask & 2u) &&
        !(s->picked & (UINT32_C(1)<<session->bindings.concept_art_event)))
        return 0;
    if (l->left_gate_broken &&
        !(s->triggered & (UINT32_C(1)<<session->bindings.left_gate_event)))
        return 0;
    return hm_overlaps(w,s->x,s->feet_y)==0;
}
int hm_level11_snapshot_encode(const hm_level11_native_session *session,
                               uint8_t *output, size_t output_size) {
    uint8_t bytes[HM_LEVEL11_SNAPSHOT_SIZE];
    const hm_state *s;
    const hm_lore_state *l;
    if (CHAR_BIT!=8 || sizeof(float)!=4u ||
        !output || output_size!=HM_LEVEL11_SNAPSHOT_SIZE ||
        !hm_level11_session_valid(session) || !state_plausible(session))
        return 0;
    s=&session->player; l=&session->lore;
    memset(bytes,0,sizeof(bytes));
    bytes[0]='H'; bytes[1]='1'; bytes[2]='S'; bytes[3]='1';
    put16(bytes+4,1u); put16(bytes+6,HM_LEVEL11_SNAPSHOT_SIZE);
    put64(bytes+8,session->world_seal);
    put32(bytes+16,session->bindings.left_gate_event);
    put32(bytes+20,session->bindings.skeletor_bio_event);
    put32(bytes+24,session->bindings.concept_art_event);
    put_float(bytes+28,s->x);
    put_float(bytes+32,s->feet_y);
    put_float(bytes+36,s->vy);
    put_float(bytes+40,s->camera_x);
    put_float(bytes+44,s->camera_y);
    put32(bytes+48,s->frame);
    put32(bytes+52,s->respawns);
    put32(bytes+56,s->landings);
    put32(bytes+60,s->hazards);
    put32(bytes+64,s->picked);
    put32(bytes+68,s->triggered);
    put32(bytes+72,(uint32_t)s->checkpoint);
    bytes[76]=s->grounded; bytes[77]=s->wall_hit;
    bytes[78]=s->ceiling_hit; bytes[79]=s->completed;
    bytes[80]=l->wall_crusher_unlocked;
    bytes[81]=l->left_gate_broken;
    bytes[82]=l->collected_mask;
    bytes[83]=l->collected_count;
    bytes[84]=session->attack_previous_down;
    put64(bytes+88,checksum(bytes,88u));
    memcpy(output,bytes,sizeof(bytes)); /* commit only after all checks */
    return 1;
}
int hm_level11_snapshot_restore(hm_level11_native_session *session,
                                const uint8_t *input, size_t input_size) {
    hm_level11_native_session next;
    uint32_t checkpoint;
    if (CHAR_BIT!=8 || sizeof(float)!=4u ||
        !input || input_size!=HM_LEVEL11_SNAPSHOT_SIZE ||
        !hm_level11_session_valid(session) ||
        memcmp(input,"H1S1",4u)!=0 ||
        input[4]!=1u || input[5]!=0u ||
        input[6]!=HM_LEVEL11_SNAPSHOT_SIZE || input[7]!=0u ||
        input[85]!=0u || input[86]!=0u || input[87]!=0u ||
        get64(input+88)!=checksum(input,88u) ||
        get64(input+8)!=session->world_seal ||
        get32(input+16)!=session->bindings.left_gate_event ||
        get32(input+20)!=session->bindings.skeletor_bio_event ||
        get32(input+24)!=session->bindings.concept_art_event ||
        input[84]>1u)
        return 0;
    next=*session;
    next.player.x=get_float(input+28);
    next.player.feet_y=get_float(input+32);
    next.player.vy=get_float(input+36);
    next.player.camera_x=get_float(input+40);
    next.player.camera_y=get_float(input+44);
    next.player.frame=get32(input+48);
    next.player.respawns=get32(input+52);
    next.player.landings=get32(input+56);
    next.player.hazards=get32(input+60);
    next.player.picked=get32(input+64);
    next.player.triggered=get32(input+68);
    checkpoint=get32(input+72);
    if (checkpoint<=INT32_MAX)
        next.player.checkpoint=(int32_t)checkpoint;
    else if (checkpoint==UINT32_MAX)
        next.player.checkpoint=-1;
    else return 0;
    next.player.grounded=input[76];
    next.player.wall_hit=input[77];
    next.player.ceiling_hit=input[78];
    next.player.completed=input[79];
    next.lore.wall_crusher_unlocked=input[80];
    next.lore.left_gate_broken=input[81];
    next.lore.collected_mask=input[82];
    next.lore.collected_count=input[83];
    next.attack_previous_down=input[84];
    if (!hm_lore_state_valid(&next.lore) || !state_plausible(&next))
        return 0;
    /* No pointers or binding seals were imported. A successful restore
     * joins ONLY the already-validated borrowed world owned by caller. */
    *session=next;
    return 1;
}
