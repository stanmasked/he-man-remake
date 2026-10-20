#ifndef HEMAN_SYNTHETIC_ROOM2_H
#define HEMAN_SYNTHETIC_ROOM2_H
#include "heman_session.h"

#define HM_ROOM2_COLUMNS 48u
#define HM_ROOM2_ROWS 24u
#define HM_ROOM2_CELLS (HM_ROOM2_COLUMNS * HM_ROOM2_ROWS)

/* Build the exact second room used by the optional Nintendo Switch course.
   Completely original synthetic training content; no iOS source assets.
   Caller retains the tile buffer throughout the game session.
   On invalid arguments, neither outputs nor tiles are modified.
   On success, outputs are committed together and the native engine's
   world/combat validators have accepted their contents. */
int hm_synthetic_room2_init(hm_world *world, hm_combat_config *combat,
                            uint8_t *tiles, uint32_t tile_count);

#endif
