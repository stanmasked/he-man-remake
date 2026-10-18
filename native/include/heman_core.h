#ifndef HEMAN_CORE_H
#define HEMAN_CORE_H

#include <stdint.h>
#include "heman_mask.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Minimal independently authored C99 host simulation. No I/O or allocations.
   Geometry uses solid/empty rectangular cells, NOT the game's slope masks.
   A front-end owns and retains all world pointers throughout execution. */
typedef enum {
    HM_OK = 0,
    HM_INVALID = 1,
    HM_COLLISION = 2,
    HM_LIMIT = 3
} hm_result;

typedef enum {
    HM_PICKUP = 1,
    HM_CHECKPOINT = 2,
    HM_HAZARD = 3,
    HM_TRIGGER = 4,
    HM_EXIT = 5
} hm_event_kind;

typedef struct {
    hm_event_kind kind;
    float x;
    float y;
    float radius;
} hm_event;

typedef struct {
    const uint8_t *solid; /* row-major, 0=empty, 1=solid; pointer borrowed */
    uint32_t columns;
    uint32_t rows;
    uint32_t tile_size;
    float spawn_x;
    float spawn_feet_y;
    float actor_half_width;
    float actor_height;
    float speed;
    float gravity;
    float jump_speed;
    float terminal_speed;
    float viewport_width;
    float viewport_height;
    float death_margin;
    const hm_event *events; /* borrowed, up to 32 */
    uint32_t event_count;
    /* Optional borrowed pixel-mask grid; NULL preserves solid-cell physics. */
    const hm_mask_grid *mask_grid;
    uint32_t max_rise; /* 0..32 pixels: optional grounded step-up */
    uint32_t max_drop; /* 0..32 pixels: optional down-slope adhesion */
} hm_world;

typedef struct {
    float axis; /* -1.0 to 1.0 */
    uint8_t jump;
    uint8_t reset;
} hm_input;

typedef struct {
    float x;
    float feet_y;
    float vy;
    float camera_x;
    float camera_y;
    uint32_t frame;
    uint32_t respawns;
    uint32_t landings;
    uint32_t hazards;
    uint32_t picked; /* bit i = pickup from event i */
    uint32_t triggered;
    int32_t checkpoint; /* -1 or event array index */
    uint8_t grounded;
    uint8_t wall_hit;
    uint8_t ceiling_hit;
    uint8_t completed;
} hm_state;

/* Initialise state at world spawn; validates complete world and initial body. */
hm_result hm_init(const hm_world *world, hm_state *state);
/* Fixed-step advance. Invalid inputs leave state unchanged. dt <= 1/30. */
hm_result hm_step(const hm_world *world, hm_state *state, hm_input input, float dt);
/* Read-only contact helper. Returns 1 on occupied body, 0 on clear body. */
int hm_overlaps(const hm_world *world, float x, float feet_y);

#ifdef __cplusplus
}
#endif
#endif
