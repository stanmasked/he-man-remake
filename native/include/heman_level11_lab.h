#ifndef HEMAN_LEVEL11_LAB_H
#define HEMAN_LEVEL11_LAB_H

#include "heman_level11_native_session.h"
#include "heman_level11_snapshot.h"
#include <stddef.h>
#include <stdint.h>

#define HM_LORE_LAB_COLS 32u
#define HM_LORE_LAB_ROWS 12u
#define HM_LORE_LAB_CELLS (HM_LORE_LAB_COLS * HM_LORE_LAB_ROWS)

/* Dev-only, fictional test world and button bits. These coordinates and
 * trigger roles ARE NOT original iOS data. No IPA data is ever linked. */
enum {
    HM_LAB_LEFT = 1u << 0,
    HM_LAB_RIGHT = 1u << 1,
    HM_LAB_JUMP = 1u << 2,
    HM_LAB_ATTACK = 1u << 3,
    HM_LAB_WALL_UPGRADE = 1u << 4,
    HM_LAB_RESET = 1u << 5,
    HM_LAB_SAVE = 1u << 6,
    HM_LAB_LOAD = 1u << 7
};

typedef struct {
    uint8_t data[HM_LEVEL11_SNAPSHOT_SIZE];
    uint8_t valid;
} hm_level11_lab_save;

/* world descriptor and solid array must outlive session. */
hm_lore_result hm_level11_lab_init(hm_world *world, uint8_t *solid,
                                  size_t capacity,
                                  hm_level11_native_session *session);

/* Every valid input is handled by the EXACT same source used by the
 * optional Switch NRO and host tests. Actions take priority:
 * reset > load > save > upgrade > ordinary move+jump+attack.
 * Events never originate from externally claimed collision flags. */
hm_lore_result hm_level11_lab_tick(hm_level11_native_session *session,
                                  hm_level11_lab_save *save,
                                  uint32_t held, uint32_t down);

#endif
