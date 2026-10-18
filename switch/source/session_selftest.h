#ifndef HEMAN_SESSION_SELFTEST_H
#define HEMAN_SESSION_SELFTEST_H

/* Independent no-assets/no-libnx C99 verification of the combined synthetic
   gameplay system. This is not evidence of a real emulator boot. */
typedef enum {
    HM_SESSION_SELFTEST_OK = 0,
    HM_SESSION_SELFTEST_INIT = 1,
    HM_SESSION_SELFTEST_MOVEMENT = 2,
    HM_SESSION_SELFTEST_HAZARD = 3,
    HM_SESSION_SELFTEST_DEFEAT = 4,
    HM_SESSION_SELFTEST_ROLLBACK = 5,
    HM_SESSION_SELFTEST_PICKUP = 6
} hm_session_selftest_code;

hm_session_selftest_code hm_session_selftest(void);
#endif
