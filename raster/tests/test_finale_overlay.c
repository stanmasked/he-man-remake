/* Synthetic finale panel: strict pixel, no-write and row canary tests. */
#include "finale_overlay.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define W 640u
#define H 360u
#define STRIDE 643u
#define SENTINEL UINT32_C(0xdead1234)
static struct {uint32_t before;uint32_t pixels[H*STRIDE];uint32_t after;} g;

int main(void) {
    uint32_t i,y;
    g.before=UINT32_C(0x11223344);
    g.after=UINT32_C(0x55667788);
    for(i=0u;i<H*STRIDE;++i)g.pixels[i]=SENTINEL;
    assert(!hm_finale_overlay(NULL,W,H,STRIDE,1u,1u,0u));
    assert(!hm_finale_overlay(g.pixels,W-1u,H,STRIDE,1u,1u,0u));
    assert(!hm_finale_overlay(g.pixels,W,H,639u,1u,1u,0u));
    assert(!hm_finale_overlay(g.pixels,W,H,5000u,1u,1u,0u));
    assert(!hm_finale_overlay(g.pixels,W,H,STRIDE,2u,1u,0u));
    assert(!hm_finale_overlay(g.pixels,W,H,STRIDE,1u,2u,0u));
    assert(!hm_finale_overlay(g.pixels,W,H,STRIDE,1u,1u,2u));
    assert(hm_finale_overlay(g.pixels,W,H,STRIDE,0u,1u,0u));
    assert(hm_finale_overlay(g.pixels,W,H,STRIDE,1u,0u,0u));
    assert(hm_finale_overlay(g.pixels,W,H,STRIDE,1u,1u,1u));
    assert(g.pixels[120u*STRIDE+208u]==SENTINEL);
    assert(hm_finale_overlay(g.pixels,W,H,STRIDE,1u,1u,0u));
    assert(g.pixels[120u*STRIDE+208u]==UINT32_C(0xffe1c86d));
    assert(g.pixels[130u*STRIDE+218u]==UINT32_C(0xff1b2c46));
    assert(g.pixels[155u*STRIDE+258u]==UINT32_C(0xfff1e6bf));
    assert(g.pixels[201u*STRIDE+254u]==UINT32_C(0xff42d58a));
    /* The native FINISH panel includes a deliberate B retry keycap. */
    assert(g.pixels[210u*STRIDE+311u]==UINT32_C(0xff42d58a));
    assert(g.pixels[212u*STRIDE+313u]==UINT32_C(0xff1b2c46));
    assert(g.pixels[213u*STRIDE+315u]==UINT32_C(0xfff1e6bf));
    assert(g.pixels[215u*STRIDE+322u]==UINT32_C(0xfff1e6bf));
    assert(g.pixels[218u*STRIDE+322u]==UINT32_C(0xfff1e6bf));
    assert(g.pixels[223u*STRIDE+311u]==UINT32_C(0xff1b2c46));
    assert(g.pixels[110u*STRIDE+200u]==SENTINEL);
    for(y=0u;y<H;++y) {
        assert(g.pixels[y*STRIDE+640u]==SENTINEL);
        assert(g.pixels[y*STRIDE+641u]==SENTINEL);
        assert(g.pixels[y*STRIDE+642u]==SENTINEL);
    }
    assert(g.before==UINT32_C(0x11223344));
    assert(g.after==UINT32_C(0x55667788));
    puts("PASS: source-only FINISH panel, no spurious redraw, padding untouched");
    return 0;
}
