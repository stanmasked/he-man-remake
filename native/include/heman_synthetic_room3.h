#ifndef HEMAN_SYNTHETIC_ROOM3_H
#define HEMAN_SYNTHETIC_ROOM3_H
#include "heman_session.h"

#define HM_ROOM3_COLUMNS 56u
#define HM_ROOM3_ROWS 24u
#define HM_ROOM3_CELLS (HM_ROOM3_COLUMNS * HM_ROOM3_ROWS)

/* Independent synthetic third training arena, NOT extracted from iOS.
   This initializer does not enable stage 3 in the current two-room NRO.
   Caller owns tile storage for the whole native session. The initializer
   validates world and combat using existing game core before committing.
   Any failure must preserve every output buffer byte. */
int hm_synthetic_room3_init(hm_world *world, hm_combat_config *combat,
                            uint8_t *tiles, uint32_t tile_count);

#endif
