/* Asset-free host regression for the exact Switch runtime replay engine. */
#include "runtime_replay.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    hm_replay_report verified, again, untouched;
    assert(hm_replay_verify(&verified) == HM_REPLAY_OK);
    assert(hm_replay_verify(&again) == HM_REPLAY_OK);
    assert(memcmp(&verified, &again, sizeof(verified)) == 0);
    assert(verified.frames == 180u);
    assert(verified.picked == 1u);
    assert(verified.landings >= 1u);
    assert(verified.sword_hits >= 1u);
    assert(verified.respawns == 0u);
    memset(&untouched, 0x5A, sizeof(untouched));
    again = untouched;
    assert(hm_replay_verify(NULL) == HM_REPLAY_BAD_ARGUMENT);
    assert(memcmp(&again, &untouched, sizeof(again)) == 0);
    printf("Synthetic runtime replay PASS: hash=%08lx frames=%lu pickups=%lu landings=%lu hits=%lu\n",
           (unsigned long)verified.fingerprint,
           (unsigned long)verified.frames,
           (unsigned long)verified.picked,
           (unsigned long)verified.landings,
           (unsigned long)verified.sword_hits);
    return 0;
}
