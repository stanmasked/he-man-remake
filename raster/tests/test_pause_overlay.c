/* Source-only PAUSED HUD pixel and padding regression. */
#include "pause_overlay.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define W 640u
#define H 360u
#define STRIDE 643u
#define KEEP UINT32_C(0xdeadbeef)
static struct {
    uint32_t left;
    uint32_t pixels[STRIDE*H];
    uint32_t right;
} guarded;
int main(void) {
    uint32_t i;
    guarded.left=UINT32_C(0x11223344);
    guarded.right=UINT32_C(0xaabbccdd);
    for(i=0u;i<STRIDE*H;++i) guarded.pixels[i]=KEEP;
    /* Bad calls may not modify even one byte of the guest view. */
    assert(hm_pause_overlay(guarded.pixels,W-1u,H,STRIDE)==0);
    assert(hm_pause_overlay(guarded.pixels,W,H,639u)==0);
    assert(hm_pause_overlay(guarded.pixels,W,H,5000u)==0);
    assert(hm_pause_overlay(NULL,W,H,STRIDE)==0);
    assert(guarded.pixels[131u*STRIDE+224u]==KEEP);
    assert(hm_pause_overlay(guarded.pixels,W,H,STRIDE)==1);
    assert(guarded.pixels[131u*STRIDE+224u]==UINT32_C(0xffe1c86d));
    assert(guarded.pixels[141u*STRIDE+238u]==UINT32_C(0xff1b2c46));
    assert(guarded.pixels[162u*STRIDE+270u]==UINT32_C(0xfff1e6bf));
    assert(guarded.pixels[197u*STRIDE+260u]==UINT32_C(0xffe1c86d));
    assert(guarded.pixels[120u*STRIDE+100u]==KEEP);
    for(i=0u;i<H;++i) {
        assert(guarded.pixels[i*STRIDE+640u]==KEEP);
        assert(guarded.pixels[i*STRIDE+641u]==KEEP);
        assert(guarded.pixels[i*STRIDE+642u]==KEEP);
    }
    assert(guarded.left==UINT32_C(0x11223344));
    assert(guarded.right==UINT32_C(0xaabbccdd));
    puts("PASS: asset-free PAUSED pixels and output padding canaries");
    return 0;
}
