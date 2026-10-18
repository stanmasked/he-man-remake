#ifndef HEMAN_RUNTIME_REPLAY_H
#define HEMAN_RUNTIME_REPLAY_H
#include <stdint.h>

/* An entirely synthetic 180-frame input replay, shared by host and Switch.
   No original iOS data is read, and no emulator is launched by this code. */
typedef enum {
    HM_REPLAY_OK = 0,
    HM_REPLAY_INIT = 1,
    HM_REPLAY_STEP = 2,
    HM_REPLAY_INVARIANT = 3,
    HM_REPLAY_MISMATCH = 4,
    HM_REPLAY_BAD_ARGUMENT = 5
} hm_replay_status;

typedef struct {
    uint32_t fingerprint; /* diagnostic fingerprint of quantized state */
    uint32_t frames;
    uint32_t picked;
    uint32_t landings;
    uint32_t sword_hits;
    uint32_t respawns;
} hm_replay_report;

/* A rejected run does not modify *out. */
hm_replay_status hm_replay_run(hm_replay_report *out);
/* Execute two independent replays and compare their reports. */
hm_replay_status hm_replay_verify(hm_replay_report *out);
#endif
