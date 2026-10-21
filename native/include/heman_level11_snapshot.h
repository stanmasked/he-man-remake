#ifndef HEMAN_LEVEL11_SNAPSHOT_H
#define HEMAN_LEVEL11_SNAPSHOT_H
#include "heman_level11_native_session.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Experimental, asset-free, versioned C99 save receipt.
 * Exactly 96 bytes, canonical little-endian numbers and IEEE-754 binary32.
 * Stores NO pointers, map cells, IPA pixels, private source paths or assets.
 * Does NOT claim parity with the original iOS save/persistence model.
 *
 * Checksum is 64-bit FNV-1a for accidental corruption detection, NOT
 * cryptographic authenticity. The caller must store data safely.
 */
#define HM_LEVEL11_SNAPSHOT_SIZE 96u
int hm_level11_snapshot_encode(const hm_level11_native_session *session,
                               uint8_t *output, size_t output_size);
int hm_level11_snapshot_restore(hm_level11_native_session *session,
                                const uint8_t *input, size_t input_size);
#ifdef __cplusplus
}
#endif
#endif
