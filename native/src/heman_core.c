#include "heman_core.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#define HM_MAX_CELLS 200000u
#define HM_MAX_SWEEP 512.0f
#define HM_MAX_BODY 128.0f
#define HM_MAX_EVENTS 32u

static float clampf(float x, float a, float b) {
    return fminf(fmaxf(x, a), b);
}

static int hm_internal_finite_float(float x) {
    return isfinite(x) != 0;
}

int hm_overlaps(const hm_world *w, float x, float feet_y) {
    int32_t x0, x1, y0, y1, gx, gy;
    if (!w || (!w->solid && !w->mask_grid) || !hm_internal_finite_float(x) || !hm_internal_finite_float(feet_y) ||
        !hm_internal_finite_float(w->actor_half_width) || !hm_internal_finite_float(w->actor_height) ||
        !w->columns || !w->rows || !w->tile_size ||
        w->actor_half_width <= 0.0f || w->actor_height <= 0.0f ||
        w->actor_half_width > HM_MAX_BODY / 2.0f ||
        w->actor_height > HM_MAX_BODY ||
        w->columns > HM_MAX_CELLS / w->rows ||
        w->tile_size > 64u || w->tile_size < 1u) {
        return 1; /* do not regard malformed geometry as safe */
    }
    if (w->mask_grid) {
        const int result = hm_mask_body_overlap(w->mask_grid, x, feet_y,
                                                w->actor_half_width, w->actor_height);
        return result != 0; /* malformed masks fail closed */
    }
    /* Avoid float->int overflow, with a finite game-space safety envelope. */
    if (fabsf(x) > 1000000.0f || fabsf(feet_y) > 1000000.0f) {
        return 1;
    }
    /* Half-open body rectangle; feet touching floor exactly is not overlap. */
    x0 = (int32_t)floorf((x - w->actor_half_width) / (float)w->tile_size);
    x1 = (int32_t)floorf(nextafterf(x + w->actor_half_width, -INFINITY) /
                        (float)w->tile_size);
    y0 = (int32_t)floorf((feet_y - w->actor_height) / (float)w->tile_size);
    y1 = (int32_t)floorf(nextafterf(feet_y, -INFINITY) / (float)w->tile_size);
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 >= (int32_t)w->columns) x1 = (int32_t)w->columns - 1;
    if (y1 >= (int32_t)w->rows) y1 = (int32_t)w->rows - 1;
    for (gy = y0; gy <= y1; ++gy) {
        for (gx = x0; gx <= x1; ++gx) {
            if (w->solid[(uint32_t)gy * w->columns + (uint32_t)gx]) return 1;
        }
    }
    return 0;
}

static int valid_world(const hm_world *w) {
    uint32_t i;
    const float p[] = {w->spawn_x, w->spawn_feet_y, w->actor_half_width,
        w->actor_height, w->speed, w->gravity, w->jump_speed,
        w->terminal_speed, w->viewport_width, w->viewport_height,
        w->death_margin};
    if ((!w->solid && !w->mask_grid) || !w->columns || !w->rows || !w->tile_size ||
        w->rows > HM_MAX_CELLS || w->columns > HM_MAX_CELLS / w->rows ||
        w->columns > 4096u || w->rows > 4096u || w->tile_size > 64u ||
        w->event_count > HM_MAX_EVENTS || w->max_rise > 32u || w->max_drop > 32u ||
        (w->event_count && !w->events)) return 0;
    for (i = 0; i < sizeof(p) / sizeof(p[0]); ++i) if (!hm_internal_finite_float(p[i])) return 0;
    if (w->actor_half_width <= 0 || w->actor_half_width > HM_MAX_BODY / 2 ||
        w->actor_height <= 0 || w->actor_height > HM_MAX_BODY ||
        w->speed <= 0 || w->gravity <= 0 || w->jump_speed <= 0 ||
        w->terminal_speed <= 0 || w->viewport_width < 1 ||
        w->viewport_height < 1 || w->death_margin < 0) return 0;
    if (w->mask_grid) {
        if (!hm_mask_valid(w->mask_grid) ||
            w->mask_grid->columns != w->columns ||
            w->mask_grid->rows != w->rows ||
            w->mask_grid->tile_size != w->tile_size) return 0;
    } else {
        for (i = 0; i < w->columns * w->rows; ++i)
            if (w->solid[i] > 1u) return 0;
    }
    for (i = 0; i < w->event_count; ++i) {
        const hm_event *e = &w->events[i];
        if (e->kind < HM_PICKUP || e->kind > HM_EXIT ||
            !hm_internal_finite_float(e->x) || !hm_internal_finite_float(e->y) || !hm_internal_finite_float(e->radius) ||
            e->radius < 1 || e->radius > 128) return 0;
        if (e->kind == HM_CHECKPOINT && hm_overlaps(w, e->x, e->y)) return 0;
    }
    return !hm_overlaps(w, w->spawn_x, w->spawn_feet_y);
}

hm_result hm_init(const hm_world *world, hm_state *state) {
    if (!world || !state || !valid_world(world)) return HM_INVALID;
    memset(state, 0, sizeof(*state));
    state->x = world->spawn_x;
    state->feet_y = world->spawn_feet_y;
    state->checkpoint = -1;
    return HM_OK;
}

/* hm_step validates borrowed masks once at frame entry. Arrays must not be
   mutated concurrently while the step is running. This avoids a full-grid
   validation for each pixel-accurate collision sample. */
static int step_overlap(const hm_world *w, float x, float feet) {
    if (w->mask_grid) {
        const int result = hm_mask_body_overlap_prevalidated(
            w->mask_grid, x, feet, w->actor_half_width, w->actor_height);
        return result != 0; /* invalid numeric coordinates fail closed */
    }
    return hm_overlaps(w, x, feet);
}

static int supported(const hm_world *w, float x, float feet) {
    return step_overlap(w, x, feet + 0.25f);
}

/* Returns last safe coordinate and collision flag. Rigid rectangular tiles. */
static float sweep(const hm_world *w, float x, float feet, float delta,
                   int horizontal, int *hit) {
    const float start = horizontal ? x : feet;
    const int n = (int)ceilf(fabsf(delta));
    float previous = start;
    int i;
    *hit = 0;
    if (n == 0) return start;
    for (i = 1; i <= n; ++i) {
        const float candidate = start + delta * (float)i / (float)n;
        const float cx = horizontal ? candidate : x;
        const float cy = horizontal ? feet : candidate;
        if (step_overlap(w, cx, cy)) {
            float safe = previous, blocked = candidate;
            int k;
            for (k = 0; k < 14; ++k) {
                const float mid = (safe + blocked) * 0.5f;
                if (step_overlap(w, horizontal ? mid : x,
                                horizontal ? feet : mid)) blocked = mid;
                else safe = mid;
            }
            *hit = 1;
            return safe;
        }
        previous = candidate;
    }
    return start + delta;
}

/* Opt-in masked slope handling. The entire body must clear each lift and
   horizontal step, and the destination must have bounded vertical support.
   Returns 1 if the grounded motion was completed. The legacy solid-cell
   stepping path is not changed when mask_grid == NULL. */
static int follow_slope(const hm_world *w, hm_state *s, float dx) {
    float horizontal, foot, raised, advanced;
    int blocked, collision, rise;
    const float before = s->feet_y;
    if (!w->mask_grid || !s->grounded || !supported(w,s->x,before))
        return 0;
    horizontal = sweep(w,s->x,before,dx,1,&blocked);
    if (blocked && dx != 0.0f && w->max_rise) {
        for (rise=1; rise<=(int)w->max_rise; ++rise) {
            raised = sweep(w,s->x,before,-(float)rise,0,&collision);
            if (collision || fabsf(raised-(before-(float)rise))>0.0001f) break;
            advanced = sweep(w,s->x,raised,dx,1,&collision);
            if (collision) continue;
            foot = sweep(w,advanced,raised,(float)rise+(float)w->max_drop+0.5f,
                         0,&collision);
            if (collision && foot <= before + (float)w->max_drop + 0.0001f) {
                s->x=advanced; s->feet_y=foot; s->vy=0;
                s->grounded=1; s->wall_hit=0; s->ceiling_hit=0;
                return 1;
            }
        }
        return 0; /* wall or ceiling: normal sweep reports wall contact */
    }
    if (!blocked) {
        foot = sweep(w,horizontal,before,(float)w->max_drop+0.5f,0,&collision);
        if (collision && foot <= before+(float)w->max_drop+0.0001f) {
            s->x=horizontal; s->feet_y=foot; s->vy=0;
            s->grounded=1; s->wall_hit=0; s->ceiling_hit=0;
            return 1;
        }
    }
    return 0; /* walk-off or wall handled by default swept fall logic */
}

static void respawn(const hm_world *w, hm_state *s) {
    if (s->checkpoint >= 0) {
        const hm_event *e = &w->events[s->checkpoint];
        s->x = e->x;
        s->feet_y = e->y;
    } else {
        s->x = w->spawn_x;
        s->feet_y = w->spawn_feet_y;
    }
    s->vy = 0;
    s->grounded = 0;
    s->wall_hit = 0;
    s->ceiling_hit = 0;
    s->respawns++;
}

static int touches(const hm_world *w, const hm_event *e, float x, float feet) {
    const float dx = fmaxf(0.0f, fabsf(e->x - x) - w->actor_half_width);
    const float top = feet - w->actor_height;
    const float dy = fmaxf(0.0f, fmaxf(top - e->y, e->y - feet));
    return dx * dx + dy * dy <= e->radius * e->radius;
}

static int crossed(const hm_world *w, const hm_event *e,
                   float px, float py, float x, float feet, int teleported) {
    const float dx = x - px, dy = feet - py;
    int i, steps;
    if (teleported) return touches(w, e, x, feet);
    steps = (int)ceilf(fmaxf(fabsf(dx), fabsf(dy)));
    if (steps > (int)HM_MAX_SWEEP) return touches(w, e, x, feet);
    if (steps < 1) steps = 1;
    for (i = 0; i <= steps; ++i) {
        const float t = (float)i / (float)steps;
        if (touches(w, e, px + dx * t, py + dy * t)) return 1;
    }
    return 0;
}

hm_result hm_step(const hm_world *w, hm_state *state, hm_input input, float dt) {
    hm_state s;
    float old_x, old_feet, dx, dy, target, max_scroll_x, max_scroll_y, factor;
    uint32_t i;
    int hit, teleported = 0, hazard = 0;
    if (!w || !state || (!w->solid && !w->mask_grid) || !hm_internal_finite_float(dt) || dt <= 0.0f || dt > 1.0f / 30.0f ||
        !hm_internal_finite_float(input.axis) || fabsf(input.axis) > 1.0f ||
        !hm_internal_finite_float(state->x) || !hm_internal_finite_float(state->feet_y) || !hm_internal_finite_float(state->vy) ||
        !hm_internal_finite_float(state->camera_x) || !hm_internal_finite_float(state->camera_y) ||
        state->checkpoint < -1 || state->checkpoint >= (int32_t)w->event_count ||
        state->frame == UINT32_MAX || state->respawns == UINT32_MAX ||
        state->landings == UINT32_MAX || state->hazards == UINT32_MAX) return HM_INVALID;
    dx = input.axis * w->speed * dt;
    dy = (fminf(state->vy + w->gravity * dt, w->terminal_speed)) * dt;
    if (!hm_internal_finite_float(dx) || !hm_internal_finite_float(dy) || fabsf(dx) > HM_MAX_SWEEP ||
        fabsf(dy) > HM_MAX_SWEEP || w->event_count > HM_MAX_EVENTS) return HM_LIMIT;
    if (w->mask_grid && (!hm_mask_valid(w->mask_grid) ||
        w->mask_grid->columns != w->columns ||
        w->mask_grid->rows != w->rows ||
        w->mask_grid->tile_size != w->tile_size)) return HM_INVALID;
    if (step_overlap(w, state->x, state->feet_y)) return HM_COLLISION;
    s = *state;
    old_x = state->x; old_feet = state->feet_y;
    s.frame++;
    if (input.reset) {
        respawn(w, &s);
        teleported = 1;
    } else {
        if (s.grounded && !input.jump && w->mask_grid &&
            follow_slope(w,&s,dx)) goto physics_finished;
        s.x = sweep(w, s.x, s.feet_y, dx, 1, &hit);
        s.wall_hit = (uint8_t)hit;
        s.ceiling_hit = 0;
        if (s.grounded && supported(w, s.x, s.feet_y)) {
            if (input.jump) {s.vy = -w->jump_speed; s.grounded = 0;}
            else s.vy = 0;
        } else {
            if (s.grounded) s.vy = 0;
            s.grounded = 0;
        }
        if (!s.grounded) {
            s.vy = fminf(s.vy + w->gravity * dt, w->terminal_speed);
            if (fabsf(s.vy * dt) > HM_MAX_SWEEP) return HM_LIMIT;
            s.feet_y = sweep(w, s.x, s.feet_y, s.vy * dt, 0, &hit);
            if (hit) {
                s.ceiling_hit = (uint8_t)(s.vy < 0);
                s.grounded = (uint8_t)(s.vy >= 0);
                s.vy = 0;
            }
        }
        if (s.feet_y > (float)(w->rows * w->tile_size) + w->death_margin) {
            respawn(w, &s);
            teleported = 1;
        }
    }
physics_finished:
    for (i = 0; i < w->event_count; ++i) {
        const hm_event *e = &w->events[i];
        if (!crossed(w, e, old_x, old_feet, s.x, s.feet_y, teleported)) continue;
        if (e->kind == HM_PICKUP) s.picked |= UINT32_C(1) << i;
        if (e->kind == HM_TRIGGER) s.triggered |= UINT32_C(1) << i;
        if (e->kind == HM_CHECKPOINT) s.checkpoint = (int32_t)i;
        if (e->kind == HM_EXIT) s.completed = 1;
        if (e->kind == HM_HAZARD) hazard = 1;
    }
    if (hazard) {
        respawn(w, &s);
        s.hazards++;
    }
    if (s.grounded && !state->grounded) s.landings++;
    max_scroll_x = fmaxf(0, (float)(w->columns * w->tile_size) - w->viewport_width);
    max_scroll_y = fmaxf(0, (float)(w->rows * w->tile_size) - w->viewport_height);
    target = clampf(s.x - w->viewport_width * 0.42f, 0, max_scroll_x);
    factor = fminf(1, dt * 10.0f);
    s.camera_x = clampf(s.camera_x + factor * (target - s.camera_x), 0, max_scroll_x);
    target = clampf(s.feet_y - w->viewport_height * 0.64f, 0, max_scroll_y);
    s.camera_y = clampf(s.camera_y + factor * (target - s.camera_y), 0, max_scroll_y);
    *state = s;
    return HM_OK;
}
