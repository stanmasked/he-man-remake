#include "third_room_marker.h"
#include "stage_marker.h"

#define GOLD UINT32_C(0xffe1c86d)
#define FACE UINT32_C(0xff354967)
#define WHITE UINT32_C(0xfff1e6bf)

static void fill(uint32_t *pixels, uint32_t stride,
                 unsigned x, unsigned y, unsigned w, unsigned h,
                 uint32_t c) {
    unsigned row,col;
    for (row=y;row<y+h;++row)
        for (col=x;col<x+w;++col)
            pixels[row*stride+col]=c;
}

int hm_three_room_marker(uint32_t *pixels, uint32_t width,
                         uint32_t height, uint32_t stride, uint8_t stage) {
    static const char three[]="111001111001111";
    unsigned row,col;
    if(!pixels || width!=640u || height!=360u ||
       stride<640u || stride>4096u || stage>2u) return 0;
    if(stage<2u)
        return hm_stage_marker(pixels,width,height,stride,stage);
    fill(pixels,stride,393u,4u,34u,29u,GOLD);
    fill(pixels,stride,396u,7u,28u,23u,FACE);
    for(row=0u;row<5u;++row)
        for(col=0u;col<3u;++col)
            if(three[row*3u+col]=='1')
                fill(pixels,stride,404u+col*4u,9u+row*4u,
                     4u,4u,WHITE);
    return 1;
}
