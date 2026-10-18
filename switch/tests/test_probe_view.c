/* Host-only tests for the same character-grid view compiled into the NRO.
   No Nintendo SDK, original IPA, images or external fixtures required. */
#include "probe_view.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint8_t tiles[48u * 24u];

int main(void) {
    hm_world w;
    hm_state s;
    struct {
        char text[HM_PROBE_BYTES];
        char guard;
    } output;
    const hm_event events[] = {
        { HM_PICKUP, 80.0f, 240.0f, 8.0f },
        { HM_CHECKPOINT, 96.0f, 240.0f, 8.0f },
        { HM_HAZARD, 112.0f, 240.0f, 8.0f },
        { HM_EXIT, 128.0f, 240.0f, 8.0f }
    };
    unsigned col;
    memset(&w, 0, sizeof(w));
    memset(&s, 0, sizeof(s));
    memset(tiles, 0, sizeof(tiles));
    for (col = 0; col < 48u; ++col) tiles[17u * 48u + col] = 1u;
    w.solid = tiles;
    w.columns = 48u;
    w.rows = 24u;
    w.tile_size = 16u;
    w.actor_height = 22.0f;
    w.events = events;
    w.event_count = 4u;
    s.x = 50.0f;
    s.feet_y = 272.0f;
    s.checkpoint = -1;
    output.guard = 'Z';
    assert(hm_probe_render(&w, &s, output.text, sizeof(output.text)) == 1);
    assert(output.guard == 'Z');
    assert(output.text[16u * HM_PROBE_STRIDE + 3u] == '@');
    assert(output.text[17u * HM_PROBE_STRIDE + 3u] == '#');
    assert(output.text[15u * HM_PROBE_STRIDE + 5u] == '*');
    assert(output.text[15u * HM_PROBE_STRIDE + 6u] == 'C');
    assert(output.text[15u * HM_PROBE_STRIDE + 7u] == '!');
    assert(output.text[15u * HM_PROBE_STRIDE + 8u] == '>');
    for (col = 0; col < HM_PROBE_ROWS; ++col)
        assert(output.text[col * HM_PROBE_STRIDE + HM_PROBE_COLS] == '\0');

    /* An enemy glyph respects camera tiles and cannot erase the player. */
    assert(hm_probe_overlay_marker(&w, &s, output.text,
                                  sizeof(output.text), 144.0f, 240.0f, 'E') == 1);
    assert(output.text[15u * HM_PROBE_STRIDE + 9u] == 'E');
    assert(hm_probe_overlay_marker(&w, &s, output.text,
                                  sizeof(output.text), 50.0f, 260.0f, 'E') == 1);
    assert(output.text[16u * HM_PROBE_STRIDE + 3u] == '@');
    assert(hm_probe_overlay_marker(&w, &s, output.text,
                                  sizeof(output.text), 144.0f, 240.0f, '\\0') == 0);
    assert(output.text[15u * HM_PROBE_STRIDE + 9u] == 'E');

    s.picked = 1u;
    s.checkpoint = 1;
    assert(hm_probe_render(&w, &s, output.text, sizeof(output.text)) == 1);
    assert(output.text[15u * HM_PROBE_STRIDE + 5u] == ' ');
    assert(output.text[15u * HM_PROBE_STRIDE + 6u] == 'c');

    /* Camera offset clamps to last full 40-tile window. */
    s.x = 720.0f;
    s.camera_x = 450.0f;
    assert(hm_probe_render(&w, &s, output.text, sizeof(output.text)) == 1);
    assert(output.text[16u * HM_PROBE_STRIDE + 37u] == '@');
    assert(output.text[17u * HM_PROBE_STRIDE + 0u] == '#');

    /* Reject invalid input atomically, without touching memory. */
    memset(output.text, '~', sizeof(output.text));
    s.camera_x = -1.0f;
    assert(hm_probe_render(&w, &s, output.text, sizeof(output.text)) == 0);
    assert(output.text[0] == '~');
    assert(output.text[HM_PROBE_BYTES - 1u] == '~');
    s.camera_x = NAN;
    assert(hm_probe_render(&w, &s, output.text, sizeof(output.text)) == 0);
    s.camera_x = 0.0f;
    assert(hm_probe_render(&w, &s, output.text, HM_PROBE_BYTES - 1u) == 0);
    assert(output.text[0] == '~');
    w.event_count = 33u;
    assert(hm_probe_render(&w, &s, output.text, sizeof(output.text)) == 0);
    assert(output.text[0] == '~');
    assert(output.guard == 'Z');
    puts("Synthetic Switch probe viewport tests passed");
    return 0;
}
