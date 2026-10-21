#ifndef HEMAN_LEVEL11_DURABLE_SAVE_H
#define HEMAN_LEVEL11_DURABLE_SAVE_H

#include "heman_level11_snapshot.h"

/* Independent opt-in persistence for the fictional Switch lore lab.
 * Does NOT mirror original iOS save formats. Caller chooses an existing
 * writable directory and prefix; two fixed files "<prefix>.0.bin" and
 * "<prefix>.1.bin" are written alternately. No private source assets. */
#define HM_LEVEL11_DURABLE_SLOT_SIZE 128u

enum {
    HM_DURABLE_OK = 1,
    HM_DURABLE_EMPTY = 0,
    HM_DURABLE_IO_ERROR = -1,
    HM_DURABLE_CORRUPT = -2,
    HM_DURABLE_INCOMPATIBLE = -3
};

/* Both operations fail closed on malformed live worlds, mismatched source
 * world seals, broken/oversized/partial file bytes, or invalid version.
 * Store never mutates session, load is atomic on failure. These are
 * crash-resilient alternate slots, NOT a filesystem power-loss guarantee.
 * FNV64 protects against accidental damage, NOT malicious tampering.
 */
int hm_level11_durable_store(const char *prefix,
                             const hm_level11_native_session *session);
int hm_level11_durable_load(const char *prefix,
                            hm_level11_native_session *session);

#endif
