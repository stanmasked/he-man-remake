#include "heman_level11_native_session.h"
#include <string.h>
#include <stddef.h>

/* Only an accidental mutation detector for borrowed research fixtures.
 * FNV-1a is NOT a cryptographic assertion of commercial map provenance.
 * Hash native object representations field-by-field, never struct padding. */
static uint64_t mix_bytes(uint64_t hash, const void *data, size_t count) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t i;
    for (i = 0; i < count; ++i)
        hash = (hash ^ (uint64_t)bytes[i]) * UINT64_C(1099511628211);
    return hash;
}

static uint64_t fingerprint_world(const hm_world *w) {
    uint64_t hash = UINT64_C(14695981039346656037);
    uint32_t i;
#define FIELD(x) do { hash = mix_bytes(hash, &(x), sizeof(x)); } while (0)
    FIELD(w->columns); FIELD(w->rows); FIELD(w->tile_size);
    FIELD(w->spawn_x); FIELD(w->spawn_feet_y);
    FIELD(w->actor_half_width); FIELD(w->actor_height);
    FIELD(w->speed); FIELD(w->gravity); FIELD(w->jump_speed);
    FIELD(w->terminal_speed); FIELD(w->viewport_width);
    FIELD(w->viewport_height); FIELD(w->death_margin);
    FIELD(w->event_count); FIELD(w->max_rise); FIELD(w->max_drop);
    for (i = 0u; i < w->event_count; ++i) {
        const hm_event *e = &w->events[i];
        FIELD(e->kind); FIELD(e->x); FIELD(e->y); FIELD(e->radius);
    }
    if (w->mask_grid) {
        const hm_mask_grid *g = w->mask_grid;
        FIELD(g->columns); FIELD(g->rows);
        FIELD(g->tile_size); FIELD(g->mask_count);
        hash = mix_bytes(hash, g->tile_ids,
                         (size_t)g->columns * g->rows * sizeof(uint16_t));
        hash = mix_bytes(hash, g->mask_rows,
                         (size_t)g->mask_count * g->tile_size * sizeof(uint64_t));
    } else {
        hash = mix_bytes(hash, w->solid, (size_t)w->columns * w->rows);
    }
#undef FIELD
    return hash;
}

/* Compare array ownership and original bounds BEFORE any content scan,
 * so even a wrongly edited dimensions/count field cannot overread the
 * arrays on the path that checks for mutation. Callers retain ownership
 * of all objects and must never free them while the session is live. */
static int sealed_world_unchanged(const hm_level11_native_session *s) {
    const hm_world *w;
    if (!s || !(w = s->world) || w != s->sealed_world ||
        w->columns != s->sealed_columns ||
        w->rows != s->sealed_rows ||
        w->tile_size != s->sealed_tile_size ||
        w->event_count != s->sealed_event_count ||
        w->events != s->sealed_events ||
        w->solid != s->sealed_solid ||
        w->mask_grid != s->sealed_mask)
        return 0;
    if (w->mask_grid) {
        const hm_mask_grid *g = w->mask_grid;
        if (g->columns != s->sealed_columns ||
            g->rows != s->sealed_rows ||
            g->tile_size != s->sealed_tile_size ||
            g->mask_count != s->sealed_mask_count ||
            g->tile_ids != s->sealed_tile_ids ||
            g->mask_rows != s->sealed_mask_rows)
            return 0;
    }
    return fingerprint_world(w) == s->world_seal;
}

static int ready(const hm_level11_native_session *session) {
    return session && session->initialized == 1u &&
           session->attack_previous_down <= 1u &&
           session->bindings.left_gate_event ==
               session->sealed_bindings.left_gate_event &&
           session->bindings.skeletor_bio_event ==
               session->sealed_bindings.skeletor_bio_event &&
           session->bindings.concept_art_event ==
               session->sealed_bindings.concept_art_event &&
           sealed_world_unchanged(session) &&
           hm_level11_native_bindings_valid(session->world,
                                             &session->bindings) &&
           hm_lore_state_valid(&session->lore);
}

hm_lore_result hm_level11_session_init(
    hm_level11_native_session *session, const hm_world *world,
    const hm_level11_event_bindings *bindings) {
    hm_level11_native_session candidate;
    if (!session || !hm_level11_native_bindings_valid(world, bindings))
        return HM_LORE_INVALID;
    memset(&candidate, 0, sizeof(candidate));
    candidate.world = world;
    candidate.sealed_world = world;
    candidate.bindings = *bindings;
    candidate.sealed_bindings = *bindings;
    if (hm_init(world, &candidate.player) != HM_OK ||
        hm_lore_init(&candidate.lore) != HM_LORE_APPLIED)
        return HM_LORE_INVALID;
    candidate.sealed_events = world->events;
    candidate.sealed_solid = world->solid;
    candidate.sealed_mask = world->mask_grid;
    candidate.sealed_columns = world->columns;
    candidate.sealed_rows = world->rows;
    candidate.sealed_tile_size = world->tile_size;
    candidate.sealed_event_count = world->event_count;
    if (world->mask_grid) {
        candidate.sealed_tile_ids = world->mask_grid->tile_ids;
        candidate.sealed_mask_rows = world->mask_grid->mask_rows;
        candidate.sealed_mask_count = world->mask_grid->mask_count;
    }
    candidate.world_seal = fingerprint_world(world);
    candidate.initialized = 1u;
    *session = candidate;
    return HM_LORE_APPLIED;
}

hm_lore_result hm_level11_session_step(
    hm_level11_native_session *session, hm_input input, float dt,
    uint8_t attack_down) {
    hm_level11_native_session next;
    hm_state before;
    hm_lore_result result;
    uint8_t fresh;
    if (!ready(session) || attack_down > 1u ||
        input.jump > 1u || input.reset > 1u)
        return HM_LORE_INVALID;
    next = *session;
    before = next.player;
    fresh = (uint8_t)(attack_down && !next.attack_previous_down);
    if (hm_step(next.world, &next.player, input, dt) != HM_OK)
        return HM_LORE_INVALID;
    result = hm_level11_accept_native_frame(
        next.world, &before, &next.player, input, dt,
        fresh, &next.bindings, &next.lore);
    if (result == HM_LORE_INVALID)
        return HM_LORE_INVALID;
    next.attack_previous_down = attack_down;
    *session = next;
    return result;
}

hm_lore_result hm_level11_session_grant_wall_crusher(
    hm_level11_native_session *session, uint8_t granted) {
    hm_level11_native_session next;
    hm_lore_result result;
    if (!ready(session)) return HM_LORE_INVALID;
    next = *session;
    result = hm_lore_grant_wall_crusher(&next.lore, granted);
    if (result == HM_LORE_APPLIED)
        *session = next;
    return result;
}
