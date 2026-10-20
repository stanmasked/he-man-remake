#include "stage_marker.h"
#define WIDTH 640u
#define HEIGHT 360u
#define BORDER UINT32_C(0xffe1c86d)
#define FACE UINT32_C(0xff354967)
#define GLYPH UINT32_C(0xfff1e6bf)

static void square(uint32_t *p, uint32_t stride,
                   unsigned x,unsigned y,unsigned w,unsigned h,
                   uint32_t color) {
    unsigned row,col;
    for(row=y;row<y+h;++row)
        for(col=x;col<x+w;++col)
            p[row*stride+col]=color;
}
int hm_stage_marker(uint32_t *pixels,uint32_t width,uint32_t height,
                    uint32_t stride,uint8_t stage) {
    static const char *const numbers[2] = {
        "010110010010111", /* 1 */
        "111001111100111"  /* 2 */
    };
    unsigned row,col;
    if(!pixels || width!=WIDTH || height!=HEIGHT ||
       stride<WIDTH || stride>4096u || stage>1u) return 0;
    square(pixels,stride,393u,4u,34u,29u,BORDER);
    square(pixels,stride,396u,7u,28u,23u,FACE);
    for(row=0u;row<5u;++row)
        for(col=0u;col<3u;++col)
            if(numbers[stage][row*3u+col]=='1')
                square(pixels,stride,404u+col*4u,9u+row*4u,4u,4u,GLYPH);
    return 1;
}
