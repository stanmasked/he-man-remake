#include "third_room_marker.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define W 640u
#define H 360u
#define STRIDE 643u
#define MARK UINT32_C(0x6a616e56)
static struct {uint32_t before;uint32_t pixels[STRIDE*H];uint32_t after;} b;
static void blank(void) {
    unsigned i;
    b.before=MARK;b.after=MARK;
    for(i=0u;i<STRIDE*H;++i)b.pixels[i]=MARK;
}
int main(void) {
    unsigned y;
    blank();
    assert(!hm_three_room_marker(NULL,W,H,STRIDE,2u));
    assert(!hm_three_room_marker(b.pixels,W,H,639u,2u));
    assert(!hm_three_room_marker(b.pixels,W-1u,H,STRIDE,2u));
    assert(!hm_three_room_marker(b.pixels,W,H,STRIDE,3u));
    assert(b.pixels[4u*STRIDE+393u]==MARK);
    assert(hm_three_room_marker(b.pixels,W,H,STRIDE,0u));
    assert(b.pixels[9u*STRIDE+408u]==UINT32_C(0xfff1e6bf));
    assert(hm_three_room_marker(b.pixels,W,H,STRIDE,1u));
    assert(b.pixels[9u*STRIDE+404u]==UINT32_C(0xfff1e6bf));
    assert(hm_three_room_marker(b.pixels,W,H,STRIDE,2u));
    assert(b.pixels[9u*STRIDE+404u]==UINT32_C(0xfff1e6bf));
    assert(b.pixels[9u*STRIDE+408u]==UINT32_C(0xfff1e6bf));
    assert(b.pixels[17u*STRIDE+404u]==UINT32_C(0xfff1e6bf));
    assert(b.pixels[4u*STRIDE+393u]==UINT32_C(0xffe1c86d));
    for(y=0u;y<H;++y) {
        assert(b.pixels[y*STRIDE+640u]==MARK);
        assert(b.pixels[y*STRIDE+641u]==MARK);
        assert(b.pixels[y*STRIDE+642u]==MARK);
    }
    assert(b.before==MARK && b.after==MARK);
    puts("PASS: three-room HUD 1/2/3 with no stage or stride overflow");
    return 0;
}
