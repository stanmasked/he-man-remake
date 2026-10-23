#include "heman_native_png_upload.h"
#include <stdlib.h>
#include <string.h>

#define HM_MAX_NATIVE_PNG_EDGE 32768u

static uint32_t hm_native_edge(uint32_t value) {
    uint32_t result = 4u;
    while (result < value) result <<= 1u;
    return result;
}

hm_native_png_upload_status hm_native_png_prepare_rgba(
    const uint8_t *png_rgba, size_t png_rgba_bytes,
    uint32_t png_width, uint32_t png_height,
    int32_t native_has_alpha,
    int32_t wrap_s_code, int32_t wrap_t_code, int32_t filter_mode_code,
    int32_t texture_slot,
    uint8_t *out_allocated_rgba, size_t out_capacity,
    hm_texture_reference_binding *out_binding
) {
    uint32_t allocated_width, allocated_height;
    size_t output_bytes, input_bytes, pixel_count, row_bytes, y, i;
    uint8_t *scratch;
    hm_texture_reference_binding result;
    if (png_rgba == NULL || out_allocated_rgba == NULL || out_binding == NULL ||
        png_width == 0u || png_height == 0u ||
        png_width > HM_MAX_NATIVE_PNG_EDGE || png_height > HM_MAX_NATIVE_PNG_EDGE ||
        (native_has_alpha != 0 && native_has_alpha != 1) ||
        (wrap_s_code != 0 && wrap_s_code != 1) ||
        (wrap_t_code != 0 && wrap_t_code != 1) ||
        (filter_mode_code != 0 && filter_mode_code != 1) ||
        texture_slot < 0) return HM_NATIVE_PNG_UPLOAD_INVALID_ARGUMENT;
    allocated_width = hm_native_edge(png_width);
    allocated_height = hm_native_edge(png_height);
    if ((size_t)allocated_width > (size_t)HM_TEXTURE_REF_MAX_TEXTURE_BYTES /
                                  4u / (size_t)allocated_height)
        return HM_NATIVE_PNG_UPLOAD_LIMIT_EXCEEDED;
    pixel_count = (size_t)allocated_width * (size_t)allocated_height;
    output_bytes = pixel_count * 4u;
    input_bytes = (size_t)png_width * (size_t)png_height * 4u;
    row_bytes = (size_t)png_width * 4u;
    if (png_rgba_bytes != input_bytes || out_capacity < output_bytes)
        return HM_NATIVE_PNG_UPLOAD_INVALID_ARGUMENT;
    if (native_has_alpha == 0) {
        for (i = 3u; i < input_bytes; i += 4u)
            if (png_rgba[i] != 255u) return HM_NATIVE_PNG_UPLOAD_INVALID_ARGUMENT;
    }
    scratch = (uint8_t *)malloc(output_bytes);
    if (scratch == NULL) return HM_NATIVE_PNG_UPLOAD_ALLOCATION_FAILED;
    memset(scratch, 0, output_bytes);
    if (native_has_alpha == 0) {
        for (i = 3u; i < output_bytes; i += 4u) scratch[i] = 255u;
    }
    for (y = 0u; y < (size_t)png_height; ++y)
        memcpy(scratch + y * (size_t)allocated_width * 4u,
               png_rgba + y * row_bytes, row_bytes);
    result.texture_slot = texture_slot;
    result.width = allocated_width;
    result.height = allocated_height;
    result.rgba = out_allocated_rgba;
    result.rgba_size = output_bytes;
    result.wrap_s_code = wrap_s_code;
    result.wrap_t_code = wrap_t_code;
    result.filter_mode_code = filter_mode_code;
    memcpy(out_allocated_rgba, scratch, output_bytes);
    *out_binding = result;
    free(scratch);
    return HM_NATIVE_PNG_UPLOAD_OK;
}
