/* Stage 097: assert pixel-exact progress geometry, full frame-buffer guards,
 * and old stage 1/2 badge compatibility. No game state or guest emulator.
 * This is a HOST native sanitizer/preflight, not NeXium evidence.
 */
#include "third_room_marker.h"
#include "stage_marker.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define W 640u
#define H 360u
#define GUARD 16u
#define SENTINEL UINT32_C(0x679a5bc3)
#define GOLD UINT32_C(0xffe1c86d)
#define FACE UINT32_C(0xff354967)
#define WHITE UINT32_C(0xfff1e6bf)
#define CURSOR UINT32_C(0xffb2f82a)

typedef struct {
    uint32_t *base;
    uint32_t *pixels;
    size_t words;
    uint32_t stride;
} guarded;

static guarded make_frame(uint32_t stride) {
    guarded result;
    size_t i;
    result.stride = stride;
    result.words = (size_t)stride * H;
    result.base = (uint32_t *)malloc(
        (result.words + 2u * GUARD) * sizeof(uint32_t));
    if (!result.base) {
        fputs("Out of memory in framebuffer guard test\n", stderr);
        exit(2);
    }
    for (i = 0; i < result.words + 2u * GUARD; ++i)
        result.base[i] = SENTINEL;
    result.pixels = result.base + GUARD;
    return result;
}

static void release_frame(guarded *frame) {
    free(frame->base);
    frame->base = NULL;
    frame->pixels = NULL;
}

static int guards_intact(const guarded *frame) {
    size_t i;
    for (i = 0; i < GUARD; ++i) {
        if (frame->base[i] != SENTINEL ||
            frame->base[GUARD + frame->words + i] != SENTINEL)
            return 0;
    }
    return 1;
}

static int unchanged(const guarded *frame) {
    size_t i;
    if (!guards_intact(frame)) return 0;
    for (i = 0; i < frame->words; ++i)
        if (frame->pixels[i] != SENTINEL) return 0;
    return 1;
}

static int check_progress(const guarded *frame, float x) {
    unsigned row, col;
    unsigned cursor = 70u + (unsigned)floorf(x * 0.5f + 0.5f);
    unsigned progress_pixels = 0u;
    if (!guards_intact(frame)) return 0;
    for (row = 0; row < H; ++row)
        for (col = 0; col < frame->stride; ++col) {
            const uint32_t actual = frame->pixels[(size_t)row *
                frame->stride + col];
            uint32_t expected = SENTINEL;
            if (row >= 324u && row < 346u &&
                col >= 65u && col < 575u)
                expected = GOLD;
            if (row >= 327u && row < 343u &&
                col >= 68u && col < 572u)
                expected = FACE;
            if (row >= 327u && row < 330u &&
                (col >= 287u && col < 289u ||
                 col >= 409u && col < 411u ||
                 col >= 491u && col < 493u))
                expected = WHITE;
            if (row >= 330u && row < 340u &&
                col >= cursor && col < cursor + 4u)
                expected = CURSOR;
            if (actual == CURSOR) ++progress_pixels;
            if (actual != expected) {
                fprintf(stderr,"Frame mismatch stride=%u x=%.2f "
                        "pixel=(%u,%u) got=%08x expected=%08x\n",
                        frame->stride, (double)x, col, row,
                        (unsigned)actual, (unsigned)expected);
                return 0;
            }
        }
    return progress_pixels == 40u;
}

static int test_valid_frames(void) {
    static const float coords[] = {
        0.0f, 48.0f, 210.0f, 434.0f, 678.0f, 828.0f,
        842.0f, 900.0f
    };
    static const uint32_t strides[] = {640u, 641u, 777u, 4096u};
    size_t i, j;
    for (i = 0; i < sizeof(strides) / sizeof(strides[0]); ++i)
        for (j = 0; j < sizeof(coords) / sizeof(coords[0]); ++j) {
            guarded frame = make_frame(strides[i]);
            int ok = hm_three_room_progress(
                frame.pixels, W, H, frame.stride, coords[j]);
            int good = ok == 1 && check_progress(&frame, coords[j]);
            release_frame(&frame);
            if (!good) {
                fprintf(stderr, "Invalid progress cursor stride=%u x=%.2f\n",
                        (unsigned)strides[i], (double)coords[j]);
                return 0;
            }
        }
    return 1;
}

static int test_rejection_without_mutation(void) {
    guarded frame = make_frame(777u);
    static const float bad_x[] = {
        -0.0001f, -10.0f, 900.01f, 901.0f, 1000000.0f,
        NAN, INFINITY, -INFINITY
    };
    size_t i;
    for (i = 0; i < sizeof(bad_x) / sizeof(bad_x[0]); ++i)
        if (hm_three_room_progress(frame.pixels, W, H, frame.stride,
                                   bad_x[i]) != 0 || !unchanged(&frame)) {
            fputs("Invalid world-X was not rejected atomically\n", stderr);
            release_frame(&frame);
            return 0;
        }
    if (hm_three_room_progress(NULL, W, H, frame.stride, 48.0f) != 0 ||
        hm_three_room_progress(frame.pixels, W-1u, H, frame.stride, 48.0f) != 0 ||
        hm_three_room_progress(frame.pixels, W+1u, H, frame.stride, 48.0f) != 0 ||
        hm_three_room_progress(frame.pixels, W, H-1u, frame.stride, 48.0f) != 0 ||
        hm_three_room_progress(frame.pixels, W, H+1u, frame.stride, 48.0f) != 0 ||
        hm_three_room_progress(frame.pixels, W, H, W-1u, 48.0f) != 0 ||
        hm_three_room_progress(frame.pixels, W, H, 4097u, 48.0f) != 0 ||
        !unchanged(&frame)) {
        fputs("Bad width/height/stride mutated output\n", stderr);
        release_frame(&frame);
        return 0;
    }
    release_frame(&frame);
    return 1;
}

static int test_old_stage_compatibility(void) {
    unsigned stage;
    for (stage = 0u; stage <= 1u; ++stage) {
        guarded existing = make_frame(641u);
        guarded three = make_frame(641u);
        int pass = hm_stage_marker(existing.pixels,W,H,existing.stride,
                                   (uint8_t)stage) == 1 &&
                   hm_three_room_marker(three.pixels,W,H,three.stride,
                                        (uint8_t)stage) == 1 &&
                   memcmp(existing.base,three.base,
                          (existing.words+2u*GUARD)*sizeof(uint32_t)) == 0 &&
                   guards_intact(&existing) && guards_intact(&three);
        release_frame(&existing);
        release_frame(&three);
        if (!pass) {
            fprintf(stderr,"Old stage %u bitmap changed\n",stage+1u);
            return 0;
        }
    }
    return 1;
}

static int test_stage_three_glyph_and_guards(void) {
    static const char bits[] = "111001111001111";
    unsigned i, row, col;
    guarded frame = make_frame(4096u);
    if (hm_three_room_marker(frame.pixels,W,H,frame.stride,2u) != 1 ||
        !guards_intact(&frame)) {
        release_frame(&frame);
        return 0;
    }
    for (row = 0u; row < H; ++row)
        for (col = 0u; col < frame.stride; ++col) {
            uint32_t expected = SENTINEL;
            unsigned x, y;
            if (col >= 393u && col < 427u &&
                row >= 4u && row < 33u) expected=GOLD;
            if (col >= 396u && col < 424u &&
                row >= 7u && row < 30u) expected=FACE;
            for (i=0u;i<15u;++i) {
                x=404u+4u*(i%3u);
                y=9u+4u*(i/3u);
                if(bits[i]=='1' && col>=x && col<x+4u &&
                   row>=y && row<y+4u)expected=WHITE;
            }
            if (frame.pixels[(size_t)row*frame.stride+col]!=expected) {
                fprintf(stderr,"Stage 3 badge pixel mismatch (%u,%u)\n",
                        col,row);
                release_frame(&frame);
                return 0;
            }
        }
    release_frame(&frame);
    return 1;
}

int main(void) {
    if (!test_valid_frames() || !test_rejection_without_mutation() ||
        !test_old_stage_compatibility() ||
        !test_stage_three_glyph_and_guards()) return 1;
    puts("PASS: Stage097 third-room x=0..900 and stage-3 digit pixel/stride "
         "bounds, invalid-input atomicity, old two-room bitmap identity");
    puts("HOST source-only test, not genuine NeXium guest/frame_rx proof");
    return 0;
}
