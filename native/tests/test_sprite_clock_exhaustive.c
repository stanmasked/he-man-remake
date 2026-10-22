#include "heman_sprite_clock.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static hm_sprite_clock_result reference_advance(
    const int32_t *bounds, uint32_t count, int32_t loop_setting,
    hm_sprite_clock_state *state, uint32_t budget) {
    hm_sprite_clock_state next = *state;
    int32_t frame = next.frame_index;
    int32_t elapsed = next.elapsed_ticks;
    int32_t remaining = next.remaining_replays;
    const int32_t total = bounds[count];
    uint32_t step;
    int stopped = 0;
    for (step = 0u; step < budget; ++step) {
        int32_t candidate = (frame + 1) % (int32_t)count;
        if (candidate <= frame) {
            if (elapsed < total) {
                candidate = (int32_t)count;
            } else {
                if (loop_setting >= 0) {
                    if (remaining == 0) {
                        stopped = 1;
                        break;
                    }
                    --remaining;
                }
                if (total == 0) return HM_SPRITE_CLOCK_RANGE;
                elapsed -= total;
            }
        }
        if (elapsed < bounds[(uint32_t)candidate]) {
            stopped = 1;
            break;
        }
        frame = candidate;
    }
    if (!stopped) return HM_SPRITE_CLOCK_LIMIT;
    next.frame_index = frame;
    next.elapsed_ticks = elapsed;
    next.remaining_replays = remaining;
    *state = next;
    return HM_SPRITE_CLOCK_OK;
}

static void assert_same(hm_sprite_clock_result actual_result,
                        hm_sprite_clock_state actual,
                        hm_sprite_clock_result expected_result,
                        hm_sprite_clock_state expected) {
    assert(actual_result == expected_result);
    assert(actual.frame_index == expected.frame_index);
    assert(actual.elapsed_ticks == expected.elapsed_ticks);
    assert(actual.remaining_replays == expected.remaining_replays);
}

static unsigned pow3(unsigned n) {
    unsigned p = 1u, i;
    for (i = 0u; i < n; ++i) p *= 3u;
    return p;
}

static void test_exhaustive_small_boundary_state_space(void) {
    static const int32_t loops[] = {-1, 0, 1, 2};
    uint32_t total_cases = 0u;
    unsigned n, code;
    for (n = 1u; n <= 4u; ++n) {
        for (code = 1u; code < pow3(n); ++code) {
            int32_t bounds[5] = {0, 0, 0, 0, 0};
            unsigned digits = code, i, li;
            for (i = 0u; i < n; ++i) {
                bounds[i + 1u] = bounds[i] + (int32_t)(digits % 3u);
                digits /= 3u;
            }
            if (bounds[n] == 0) continue;
            for (li = 0u; li < sizeof loops / sizeof loops[0]; ++li) {
                const int32_t loop_setting = loops[li];
                int32_t remaining;
                const int32_t remaining_min =
                    loop_setting < 0 ? loop_setting : 0;
                const int32_t remaining_max =
                    loop_setting < 0 ? loop_setting : loop_setting;
                int32_t idx, elapsed;
                for (idx = 0; idx < (int32_t)n; ++idx) {
                    for (elapsed = 0;
                         elapsed <= 3 * bounds[n] + 2; ++elapsed) {
                        for (remaining = remaining_min;
                             remaining <= remaining_max; ++remaining) {
                            hm_sprite_clock_state actual = {
                                idx, elapsed, remaining
                            };
                            hm_sprite_clock_state expected = actual;
                            hm_sprite_clock_result ar, er;
                            er = reference_advance(
                                bounds, n, loop_setting, &expected, 64u);
                            ar = hm_sprite_clock_advance(
                                bounds, n, loop_setting, &actual, 64u);
                            assert_same(ar, actual, er, expected);
                            ++total_cases;
                        }
                    }
                }
            }
        }
    }
    assert(total_cases == 41874u);
    printf("PASS: exhaustive synthetic boundary state space (%u cases)\n",
           total_cases);
}

int main(void) {
    test_exhaustive_small_boundary_state_space();
    return 0;
}
