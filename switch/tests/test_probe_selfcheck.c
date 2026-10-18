#include "probe_selfcheck.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    /* Run twice to catch unexpected persistent state between boot probes. */
    assert(hm_probe_boot_selfcheck() == HM_PROBE_CHECK_OK);
    assert(hm_probe_boot_selfcheck() == HM_PROBE_CHECK_OK);
    puts("Synthetic boot self-check passed twice");
    return 0;
}
