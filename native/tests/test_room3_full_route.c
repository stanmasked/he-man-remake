/* Stage 090: authentic authored-room-3 native controller route.
 * This tests real fixed-step physics, enemy and hazard processing, and
 * earned HM_EXIT; it is NOT NeXium guest evidence or original iOS parity.
 * Never teleport to x=842 or alter the world, player, event or enemy state.
 */
#include "heman_air_smash.h"
#include "heman_synthetic_room3.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define MAX_FRAMES 950u
#define FRAME_DT (1.0f / 60.0f)

int main(void) {
    static uint8_t cells[HM_ROOM3_CELLS];
    hm_world world;
    hm_combat_config combat;
    hm_session session, frozen;
    hm_dash_state dash = {0u, 0u}, old_dash;
    hm_air_smash_state ability = {0}, old_ability;
    uint8_t paused = 0u;
    unsigned tick, jump_count = 0u, saw_checkpoint = 0u;
    unsigned saw_pickup = 0u, saw_hazard = 0u, saw_air = 0u;
    unsigned saw_land_after_jump = 0u;
    int success = 0;

    assert(hm_synthetic_room3_init(&world, &combat, cells,
                                   HM_ROOM3_CELLS) == 1);
    assert(hm_session_init(&world, &combat, &session) == HM_SESSION_OK);
    assert(session.player.x == 48.0f);
    assert(session.player.completed == 0u);

    /* Walk into the genuine checkpoint and hazard once, then perform a
       correctly timed D-pad Right + fresh A jump on the next attempt.
       The game, rather than this test, chooses the checkpoint respawn. */
    for (tick = 0u; tick < MAX_FRAMES; ++tick) {
        hm_input cmd = {1.0f, 0u, 0u};
        hm_session_result result;
        if (saw_hazard && jump_count == 0u &&
            session.player.x >= 660.0f &&
            session.player.x < 665.0f) {
            cmd.jump = 1u; /* one fresh A edge */
            ++jump_count;
        }
        result = hm_air_smash_step(&world, &combat, &session, &paused,
                                   &dash, &ability, 1u, cmd,
                                   0u, 0u, 0u, 0u, FRAME_DT);
        if (result != HM_SESSION_OK) {
            fprintf(stderr, "invalid gameplay result at tick %u: %d\n",
                    tick, (int)result);
            return 1;
        }
        if (session.player.picked & 1u) saw_pickup = 1u;
        if (session.player.checkpoint == 1) saw_checkpoint = 1u;
        if (jump_count && !session.player.grounded)
            saw_air = 1u;
        if (saw_air && session.player.grounded)
            saw_land_after_jump = 1u;
        if (session.player.hazards && !saw_hazard) {
            saw_hazard = 1u;
            assert(session.player.hazards == 1u);
            assert(session.player.respawns >= 1u);
            assert(session.player.checkpoint == 1);
            assert(session.player.x == 434.0f);
            assert(session.player.feet_y == 288.0f);
            assert(session.combat.player_hp == combat.player_initial_hp);
        }
        /* A second hazard means the scripted real jump missed. Never
           move goal posts or programmatically flip the CLEAR bit. */
        if (session.player.hazards > 1u) {
            fprintf(stderr,
                "route failed: hazard %u after jump %u at x=%.2f\n",
                session.player.hazards, jump_count, session.player.x);
            return 2;
        }
        if (session.player.completed) {
            success = 1;
            break;
        }
    }

    if (!success) {
        fprintf(stderr,
                "room3 goal never earned: tick=%u x=%.2f feet=%.2f "
                "hp=%u hazards=%u jump=%u\n",
                tick, session.player.x, session.player.feet_y,
                session.combat.player_hp, session.player.hazards, jump_count);
        return 3;
    }
    assert(saw_pickup && saw_checkpoint && saw_hazard);
    assert(jump_count == 1u && saw_air && saw_land_after_jump);
    assert(session.player.x >= 825.0f); /* genuine exit is x842 */
    assert(session.player.checkpoint == 1);
    assert(session.player.hazards == 1u);
    assert(session.player.completed == 1u);
    assert(paused == 0u);

    /* Source-native terminal FINISH semantics: frozen stage-3 game state
       across more than one frame, even when held movement is present. */
    frozen = session;
    old_dash = dash;
    old_ability = ability;
    for (unsigned i = 0u; i < 3u; ++i) {
        hm_input right = {1.0f, 0u, 0u};
        assert(hm_air_smash_step(&world, &combat, &session, &paused,
                                 &dash, &ability, 1u, right,
                                 0u, 0u, 0u, 0u, FRAME_DT) == HM_SESSION_OK);
        assert(memcmp(&session, &frozen, sizeof(session)) == 0);
        assert(memcmp(&dash, &old_dash, sizeof(dash)) == 0);
        assert(memcmp(&ability, &old_ability, sizeof(ability)) == 0);
    }

    /* A genuine B input on the terminal screen creates a fresh room-3
       session without modifying the stage chain, map, or ordinary NRO. */
    {
        hm_input b = {0.0f, 0u, 1u};
        assert(hm_air_smash_step(&world, &combat, &session, &paused,
                                 &dash, &ability, 1u, b,
                                 0u, 0u, 0u, 0u, FRAME_DT) == HM_SESSION_OK);
    }
    assert(session.player.x == world.spawn_x);
    assert(session.player.feet_y == world.spawn_feet_y);
    assert(session.player.frame == 0u);
    assert(session.player.completed == 0u);
    assert(session.player.checkpoint == -1);
    assert(session.player.hazards == 0u);
    assert(session.combat.enemy_hp == combat.enemy_initial_hp);
    assert(session.combat.player_hp == combat.player_initial_hp);
    assert(ability.armed == 0u && ability.cooldown == 0u);
    assert(dash.remaining == 0u && dash.recovery == 0u);

    printf("PASS: real C99 room3 spawn→pickup→checkpoint→hazard→"
           "checkpoint respawn→A jump→native CLEAR; "
           "terminal freeze and B replay (frames=%u)\n", tick + 1u);
    return 0;
}
