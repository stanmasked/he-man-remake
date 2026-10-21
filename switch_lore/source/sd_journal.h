#ifndef HEMAN_SWITCH_LORE_SD_JOURNAL_H
#define HEMAN_SWITCH_LORE_SD_JOURNAL_H

#include "heman_level11_native_session.h"

/* Optional, user-triggered, fictional lore lab SD persistence only.
 * 1 means journal read/write succeeded, 0 means unavailable/rejected.
 * No SD mounting or filesystem probing occurs during normal boot. */
int hm_switch_lore_sd_save(const hm_level11_native_session *session);
int hm_switch_lore_sd_load(hm_level11_native_session *session);

#endif
