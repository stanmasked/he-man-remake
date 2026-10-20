/* Stage 086 optional RGB status HUD with padding and sentinel guards. */
#include "air_smash_hud.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define STRIDE 643u
#define N (360u*STRIDE)
#define BEFORE UINT32_C(0x12abcdef)
#define AFTER UINT32_C(0xdecade12)
#define SENTINEL UINT32_C(0xfeedbaca)
static struct {
    uint32_t before;
    uint32_t pixels[N];
    uint32_t after;
} target;
static void reset(void) {
    uint32_t i;
    target.before=BEFORE;target.after=AFTER;
    for(i=0u;i<N;++i)target.pixels[i]=SENTINEL;
}
int main(void) {
    hm_air_smash_state ability={0};
    unsigned i;
    reset();
    assert(!hm_air_smash_hud(NULL,640u,360u,STRIDE,&ability));
    assert(!hm_air_smash_hud(target.pixels,640u,360u,STRIDE,NULL));
    assert(!hm_air_smash_hud(target.pixels,639u,360u,STRIDE,&ability));
    assert(!hm_air_smash_hud(target.pixels,640u,360u,639u,&ability));
    assert(!hm_air_smash_hud(target.pixels,640u,360u,5000u,&ability));
    ability.armed=2u;
    assert(!hm_air_smash_hud(target.pixels,640u,360u,STRIDE,&ability));
    ability.armed=0u;ability.cooldown=51u;
    assert(!hm_air_smash_hud(target.pixels,640u,360u,STRIDE,&ability));
    ability.cooldown=0u;
    assert(target.pixels[88u*STRIDE+588u]==SENTINEL);
    assert(hm_air_smash_hud(target.pixels,640u,360u,STRIDE,&ability));
    assert(target.pixels[88u*STRIDE+588u]==UINT32_C(0xff6ee0d8));
    ability.armed=1u;
    assert(hm_air_smash_hud(target.pixels,640u,360u,STRIDE,&ability));
    assert(target.pixels[88u*STRIDE+588u]==UINT32_C(0xffffaa55));
    ability.armed=0u;ability.cooldown=32u;
    assert(hm_air_smash_hud(target.pixels,640u,360u,STRIDE,&ability));
    assert(target.pixels[88u*STRIDE+588u]==UINT32_C(0xff566578));
    ability.impact_frames=8u;
    assert(hm_air_smash_hud(target.pixels,640u,360u,STRIDE,&ability));
    assert(target.pixels[88u*STRIDE+588u]==UINT32_C(0xff42d58a));
    assert(target.pixels[79u*STRIDE+575u]==UINT32_C(0xff203449));
    assert(target.pixels[70u*STRIDE+575u]==SENTINEL);
    for(i=0u;i<360u;++i) {
        assert(target.pixels[i*STRIDE+640u]==SENTINEL);
        assert(target.pixels[i*STRIDE+641u]==SENTINEL);
        assert(target.pixels[i*STRIDE+642u]==SENTINEL);
    }
    assert(target.before==BEFORE&&target.after==AFTER);
    puts("PASS: opt-in ZL HUD ready/active/cooldown/impact, no overruns");
    return 0;
}
