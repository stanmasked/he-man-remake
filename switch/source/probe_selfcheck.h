#ifndef HEMAN_PROBE_SELFCHECK_H
#define HEMAN_PROBE_SELFCHECK_H

/* Deterministic, asset-free C99 startup diagnostic, usable on a host or
   Nintendo Switch. It runs an independent scripted physics course and checks
   the event/camera/text-viewport adapters; it does NOT boot the iOS game. */
typedef enum {
    HM_PROBE_CHECK_OK = 0,
    HM_PROBE_CHECK_SETUP = 1,
    HM_PROBE_CHECK_STEP = 2,
    HM_PROBE_CHECK_STATE = 3,
    HM_PROBE_CHECK_VIEW = 4
} hm_probe_check_result;

hm_probe_check_result hm_probe_boot_selfcheck(void);
#endif
