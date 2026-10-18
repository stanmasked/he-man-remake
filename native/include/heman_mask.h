#ifndef HEMAN_MASK_H
#define HEMAN_MASK_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Asset-free borrowed arrays; mask_rows[id * tile_size + row] contains bit x.
   0xffff means empty. This is a geometry experiment, not hm_step physics. */
typedef struct {
    const uint16_t *tile_ids;
    const uint64_t *mask_rows;
    uint32_t columns, rows, tile_size, mask_count;
} hm_mask_grid;
int hm_mask_valid(const hm_mask_grid *grid);
/* 0 empty, 1 solid, -1 malformed. Off-grid is empty. */
int hm_mask_solid_at(const hm_mask_grid *grid, int32_t x, int32_t y);
/* Half-open body: 0 clear, 1 overlap, -1 invalid. */
int hm_mask_body_overlap(const hm_mask_grid *grid, float x, float feet_y,
                         float half_width, float height);
/* INTERNAL fast path: caller MUST have called hm_mask_valid on these same
   immutable borrowed arrays at the start of the current simulation tick.
   Skips the O(grid cells + mask rows) structural scan, but still validates
   body coordinates and dimensions. Do not call on untrusted arrays. */
int hm_mask_body_overlap_prevalidated(const hm_mask_grid *grid,
                                      float x, float feet_y,
                                      float half_width, float height);
/* Three foot samples, vertical scanning <= 512 px; 1 found, 0 absent, -1 bad. */
int hm_mask_feet_contact(const hm_mask_grid *grid, float x, float half_width,
                         float begin_y, float end_y, int32_t *contact_y);
#ifdef __cplusplus
}
#endif
#endif
