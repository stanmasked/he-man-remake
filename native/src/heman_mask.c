#include "heman_mask.h"
#include <math.h>
#include <stddef.h>
#define HM_MASK_MAX_CELLS 100000u
#define HM_MASK_MAX_IDS 1024u
#define HM_MASK_MAX_BODY 128.0f
#define HM_MASK_MAX_SWEEP 512
#define HM_EMPTY UINT16_MAX

int hm_mask_valid(const hm_mask_grid *g) {
    uint32_t i, y;
    uint64_t permitted;
    if (!g || !g->tile_ids || !g->mask_rows || !g->columns || !g->rows ||
        g->tile_size < 1 || g->tile_size > 64 ||
        !g->mask_count || g->mask_count > HM_MASK_MAX_IDS ||
        g->columns > HM_MASK_MAX_CELLS/g->rows) return 0;
    for (i=0; i<g->columns*g->rows; ++i) {
        if (g->tile_ids[i]!=HM_EMPTY && g->tile_ids[i]>=g->mask_count) return 0;
    }
    permitted = g->tile_size == 64 ? UINT64_MAX : (UINT64_C(1) << g->tile_size)-1;
    for (i=0; i<g->mask_count; ++i) {
        for (y=0; y<g->tile_size; ++y) {
            if (g->mask_rows[i*g->tile_size+y] & ~permitted) return 0;
        }
    }
    return 1;
}
static int solid(const hm_mask_grid *g, int32_t x, int32_t y) {
    uint32_t tile_x, tile_y, id;
    if (x<0 || y<0 || (uint32_t)x/g->tile_size>=g->columns ||
        (uint32_t)y/g->tile_size>=g->rows) return 0;
    tile_x=(uint32_t)x/g->tile_size;
    tile_y=(uint32_t)y/g->tile_size;
    id=g->tile_ids[tile_y*g->columns+tile_x];
    if (id==HM_EMPTY) return 0;
    return (int)((g->mask_rows[id*g->tile_size+((uint32_t)y%g->tile_size)] >>
                  ((uint32_t)x%g->tile_size)) & UINT64_C(1));
}
int hm_mask_solid_at(const hm_mask_grid *g, int32_t x, int32_t y) {
    return hm_mask_valid(g) ? solid(g,x,y) : -1;
}
int hm_mask_body_overlap(const hm_mask_grid *g, float x, float feet,
                         float half_width, float height) {
    int32_t lo_x, hi_x, lo_y, hi_y, ix, iy;
    if (!hm_mask_valid(g) || !isfinite(x) || !isfinite(feet) ||
        !isfinite(half_width) || !isfinite(height) ||
        half_width<=0 || 2*half_width>HM_MASK_MAX_BODY ||
        height<=0 || height>HM_MASK_MAX_BODY ||
        fabsf(x)>1000000 || fabsf(feet)>1000000) return -1;
    lo_x=(int32_t)floorf(x-half_width);
    hi_x=(int32_t)ceilf(x+half_width);
    lo_y=(int32_t)floorf(feet-height);
    hi_y=(int32_t)ceilf(feet);
    for(iy=lo_y; iy<hi_y; ++iy) {
        for(ix=lo_x;ix<hi_x;++ix) {
            if (solid(g,ix,iy)) return 1;
        }
    }
    return 0;
}
int hm_mask_feet_contact(const hm_mask_grid *g, float x, float half_width,
                         float begin_y, float end_y, int32_t *contact_y) {
    int32_t px[3], py, start, end;
    int i;
    if(!contact_y || !hm_mask_valid(g) || !isfinite(x) || !isfinite(half_width) ||
       !isfinite(begin_y) || !isfinite(end_y) || half_width<0 ||
       end_y<begin_y || end_y-begin_y>HM_MASK_MAX_SWEEP ||
       fabsf(x)>1000000 || fabsf(begin_y)>1000000 || fabsf(end_y)>1000000) return -1;
    px[0]=(int32_t)floorf(x-half_width);
    px[1]=(int32_t)floorf(x);
    px[2]=(int32_t)floorf(x+half_width);
    start=(int32_t)floorf(begin_y);
    end=(int32_t)floorf(end_y);
    for (py=start; py<=end; ++py) {
        for(i=0;i<3;++i) {
            if (solid(g,px[i],py)) { *contact_y=py;return 1; }
        }
    }
    return 0;
}
