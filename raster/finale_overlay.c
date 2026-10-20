#include "finale_overlay.h"

#define W 640u
#define H 360u
#define GOLD UINT32_C(0xffe1c86d)
#define FACE UINT32_C(0xff1b2c46)
#define LETTER UINT32_C(0xfff1e6bf)
#define ACCENT UINT32_C(0xff42d58a)

static void fill(uint32_t *pixels, uint32_t stride,
                 unsigned x, unsigned y, unsigned w, unsigned h,
                 uint32_t color) {
    unsigned row, col;
    for (row = y; row < y + h; ++row)
        for (col = x; col < x + w; ++col)
            pixels[row*stride + col] = color;
}

int hm_finale_overlay(uint32_t *pixels, uint32_t width, uint32_t height,
                      uint32_t stride, uint8_t stage, uint8_t completed,
                      uint8_t paused) {
    static const char *const glyph[6] = {
        "111100110100100", /* F */
        "111010010010111", /* I */
        "101111111111101", /* N */
        "111010010010111", /* I */
        "111100111001111", /* S */
        "101101111101101"  /* H */
    };
    unsigned ch, row, col;
    if (!pixels || width != W || height != H ||
        stride < W || stride > 4096u || stage > 1u ||
        completed > 1u || paused > 1u) return 0;

    if (stage != 1u || !completed || paused) return 1;
    fill(pixels, stride, 208u, 120u, 224u, 110u, GOLD);
    fill(pixels, stride, 213u, 125u, 214u, 100u, FACE);
    for (ch = 0u; ch < 6u; ++ch)
        for (row = 0u; row < 5u; ++row)
            for (col = 0u; col < 3u; ++col)
                if (glyph[ch][row*3u+col] == '1')
                    fill(pixels, stride, 258u+ch*22u+col*5u,
                         155u+row*6u, 5u, 6u, LETTER);
    /* Simple bright underline leaves an obvious optical victory receipt. */
    fill(pixels, stride, 254u, 201u, 132u, 5u, ACCENT);
    /* A literal B-button prompt in the same independent bitmap.
       White 3x5 glyph within a green keycap, not a commercial asset. */
    fill(pixels, stride, 311u, 210u, 18u, 13u, ACCENT);
    fill(pixels, stride, 313u, 212u, 14u, 9u, FACE);
    fill(pixels, stride, 315u, 213u, 2u, 7u, LETTER);
    fill(pixels, stride, 317u, 213u, 5u, 2u, LETTER);
    fill(pixels, stride, 322u, 215u, 2u, 2u, LETTER);
    fill(pixels, stride, 317u, 216u, 5u, 2u, LETTER);
    fill(pixels, stride, 322u, 218u, 2u, 2u, LETTER);
    fill(pixels, stride, 317u, 219u, 5u, 1u, LETTER);
    return 1;
}
