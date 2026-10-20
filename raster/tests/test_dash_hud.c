/* Standalone ZR HUD render proof; never uses proprietary artwork. */
#include "dash_hud.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define W 640u
#define H 360u
#define STRIDE 643u
#define CANARY UINT32_C(0x1a2b3c4d)
static struct {
    uint32_t pre;
    uint32_t pixels[STRIDE*H];
    uint32_t post;
} buf;
int main(void) {
    hm_dash_state ready={0u,0u},active={6u,74u},cooling={0u,40u};
    hm_dash_state invalid={13u,0u};
    unsigned row,i;
    buf.pre=CANARY;buf.post=CANARY;
    for(i=0u;i<STRIDE*H;++i)buf.pixels[i]=CANARY;
    assert(hm_dash_hud(NULL,W,H,STRIDE,&ready)==0);
    assert(hm_dash_hud(buf.pixels,W-1u,H,STRIDE,&ready)==0);
    assert(hm_dash_hud(buf.pixels,W,H,STRIDE-5u,&ready)==0);
    assert(hm_dash_hud(buf.pixels,W,H,STRIDE,&invalid)==0);
    assert(hm_dash_hud(buf.pixels,W,H,STRIDE,NULL)==0);
    assert(buf.pixels[9u*STRIDE+432u]==CANARY);
    assert(hm_dash_hud(buf.pixels,W,H,STRIDE,&ready)==1);
    assert(buf.pixels[9u*STRIDE+432u]==UINT32_C(0xffe1c86d));
    assert(buf.pixels[16u*STRIDE+437u]==UINT32_C(0xff6ee0d8));
    assert(buf.pixels[16u*STRIDE+466u]==UINT32_C(0xff6ee0d8));
    assert(hm_dash_hud(buf.pixels,W,H,STRIDE,&active)==1);
    assert(buf.pixels[16u*STRIDE+437u]==UINT32_C(0xffffaa55));
    assert(buf.pixels[16u*STRIDE+452u]==UINT32_C(0xff1b2c46));
    assert(hm_dash_hud(buf.pixels,W,H,STRIDE,&cooling)==1);
    assert(buf.pixels[16u*STRIDE+437u]==UINT32_C(0xff566578));
    assert(buf.pixels[16u*STRIDE+462u]==UINT32_C(0xff1b2c46));
    assert(buf.pixels[8u*STRIDE+440u]==CANARY);
    for(row=0u;row<H;++row) {
        assert(buf.pixels[row*STRIDE+640u]==CANARY);
        assert(buf.pixels[row*STRIDE+641u]==CANARY);
        assert(buf.pixels[row*STRIDE+642u]==CANARY);
    }
    assert(buf.pre==CANARY && buf.post==CANARY);
    puts("PASS: stage-2 ZR dash ready/active/recovery pixels and stride");
    return 0;
}
