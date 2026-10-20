/* Two-scene synthetic HUD tile test, including framebuffer padding canaries. */
#include "stage_marker.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define W 640u
#define H 360u
#define STRIDE 643u
#define CANARY UINT32_C(0x12345678)
static struct {
    uint32_t prefix;
    uint32_t pixels[STRIDE*H];
    uint32_t suffix;
} guard;
int main(void) {
    unsigned i;
    guard.prefix=CANARY;
    guard.suffix=CANARY;
    for(i=0u;i<STRIDE*H;++i)guard.pixels[i]=CANARY;
    assert(hm_stage_marker(NULL,W,H,STRIDE,0u)==0);
    assert(hm_stage_marker(guard.pixels,W,H,STRIDE,2u)==0);
    assert(hm_stage_marker(guard.pixels,W-1u,H,STRIDE,0u)==0);
    assert(hm_stage_marker(guard.pixels,W,H,639u,0u)==0);
    assert(guard.pixels[4u*STRIDE+393u]==CANARY);
    assert(hm_stage_marker(guard.pixels,W,H,STRIDE,0u)==1);
    assert(guard.pixels[4u*STRIDE+393u]==UINT32_C(0xffe1c86d));
    assert(guard.pixels[15u*STRIDE+404u]==UINT32_C(0xff354967));
    assert(guard.pixels[9u*STRIDE+408u]==UINT32_C(0xfff1e6bf)); /* 1 top center */
    assert(guard.pixels[9u*STRIDE+404u]==UINT32_C(0xff354967));
    assert(hm_stage_marker(guard.pixels,W,H,STRIDE,1u)==1);
    assert(guard.pixels[9u*STRIDE+404u]==UINT32_C(0xfff1e6bf)); /* 2 upper left */
    assert(guard.pixels[12u*STRIDE+200u]==CANARY);
    for(i=0u;i<H;++i) {
        assert(guard.pixels[i*STRIDE+640u]==CANARY);
        assert(guard.pixels[i*STRIDE+641u]==CANARY);
        assert(guard.pixels[i*STRIDE+642u]==CANARY);
    }
    assert(guard.prefix==CANARY && guard.suffix==CANARY);
    puts("PASS: stage-1/stage-2 HUD overlay and padding guards");
    return 0;
}
