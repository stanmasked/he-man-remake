#include "session_selftest.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    assert(hm_session_selftest() == HM_SESSION_SELFTEST_OK);
    assert(hm_session_selftest() == HM_SESSION_SELFTEST_OK);
    puts("Combined gameplay startup self-check passed twice");
    return 0;
}
