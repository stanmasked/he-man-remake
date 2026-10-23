#ifndef HEMAN_NATIVE_PNG_UPLOAD_H
#define HEMAN_NATIVE_PNG_UPLOAD_H
#include <stddef.h>
#include <stdint.h>
#include "heman_textured_quad_reference.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef enum hm_native_png_upload_status {
    HM_NATIVE_PNG_UPLOAD_OK = 0,
    HM_NATIVE_PNG_UPLOAD_INVALID_ARGUMENT = 1,
    HM_NATIVE_PNG_UPLOAD_LIMIT_EXCEEDED = 2,
    HM_NATIVE_PNG_UPLOAD_ALLOCATION_FAILED = 3
} hm_native_png_upload_status;

/* Asset-free C99 upload model based on verified Stage223 native callbacks.
 * Input is decoded, alpha-transformed PNG RGBA. Native RGB has implicit
 * sampled alpha=255; native RGBA retains alpha. Right/bottom missing pixels
 * occupy min-four, next-power-of-two allocation and have zero native bytes.
 * No original assets, runtime GPU submission or camera parity are implied.
 * On failure output bytes and binding remain unchanged. Overlap between
 * input and output is supported using a bounded scratch allocation. */
hm_native_png_upload_status hm_native_png_prepare_rgba(
    const uint8_t *png_rgba, size_t png_rgba_bytes,
    uint32_t png_width, uint32_t png_height,
    int32_t native_has_alpha,
    int32_t wrap_s_code, int32_t wrap_t_code, int32_t filter_mode_code,
    int32_t texture_slot,
    uint8_t *out_allocated_rgba, size_t out_capacity,
    hm_texture_reference_binding *out_binding
);
#ifdef __cplusplus
}
#endif
#endif
