#include "pause_overlay.h"

#define PW 640u
#define PH 360u
#define PANEL UINT32_C(0xff1b2c46)
#define BORDER UINT32_C(0xffe1c86d)
#define LETTER UINT32_C(0xfff1e6bf)

static void fill(uint32_t *p, uint32_t stride, unsigned x, unsigned y,
                 unsigned w, unsigned h, uint32_t color) {
    unsigned row, col;
    for (row=y; row<y+h; ++row)
        for (col=x; col<x+w; ++col)
            p[row*stride+col]=color;
}

int hm_pause_overlay(uint32_t *pixels, uint32_t width,
                     uint32_t height, uint32_t stride) {
    static const char *const glyph[6] = {
        "111101111100100", /* P */
        "010101111101101", /* A */
        "101101101101111", /* U */
        "111100111001111", /* S */
        "111100110100111", /* E */
        "110101101101110"  /* D */
    };
    unsigned ch,row,col;
    if (!pixels || width!=PW || height!=PH ||
        stride<width || stride>4096u) return 0;
    fill(pixels,stride,224u,131u,192u,92u,BORDER);
    fill(pixels,stride,228u,135u,184u,84u,PANEL);
    for (ch=0u;ch<6u;++ch)
        for (row=0u;row<5u;++row)
            for (col=0u;col<3u;++col)
                if (glyph[ch][row*3u+col]=='1')
                    fill(pixels,stride,270u+ch*17u+col*4u,
                         162u+row*5u,4u,5u,LETTER);
    fill(pixels,stride,260u,197u,121u,5u,BORDER);
    return 1;
}
