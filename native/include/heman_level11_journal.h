#ifndef HEMAN_LEVEL11_JOURNAL_H
#define HEMAN_LEVEL11_JOURNAL_H

#include "heman_level11_snapshot.h"
#include <stddef.h>
#include <stdint.h>

/* Experimental 120-byte bounded dual-slot on-disk container.
 * Slots are independent and may be persisted between application starts.
 * Recovery prefers the newest intact + source-world-compatible slot.
 * Not encryption, not original iOS save data, not power-loss durability proof.
 */
#define HM_LEVEL11_JOURNAL_RECORD_SIZE 120u
typedef struct {
    void *context;
    /* 1: exact 120 bytes, 0: missing, truncated or unreadable. */
    int (*read_slot)(void *context, unsigned slot,
                     uint8_t output[HM_LEVEL11_JOURNAL_RECORD_SIZE]);
    /* 1 only when all 120 bytes were accepted, 0 on failure.
     * Caller owns flushing/closing and the directory/file lifetimes. */
    int (*write_slot)(void *context, unsigned slot,
                      const uint8_t data[HM_LEVEL11_JOURNAL_RECORD_SIZE]);
} hm_level11_journal_io;

/* Returns 1 on success, 0 on absent/invalid/incompatible/unwritable.
 * Failed calls preserve the live C99 session bytes and (for restore) the
 * generation output. A failed write may corrupt ONLY the target slot;
 * the prior known-good slot must not be touched by the callback.
 */
int hm_level11_journal_store(const hm_level11_native_session *session,
                             const hm_level11_journal_io *io,
                             uint64_t *generation);
int hm_level11_journal_restore(hm_level11_native_session *session,
                               const hm_level11_journal_io *io,
                               uint64_t *generation);

#endif
