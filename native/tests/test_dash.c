/* Stage 069: real second-room physics dash, no commercial iOS resources. */
#include "heman_dash.h"
#include "heman_synthetic_room2.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    hm_world room,invalid;
    hm_combat_config combat;
    hm_session game,before,baseline;
    hm_dash_state dash={0u,0u},before_dash;
    hm_input idle={0.0f,0u,0u},right={1.0f,0u,0u};
    uint8_t paused=0u, before_paused;
    uint8_t tiles[HM_ROOM2_CELLS];
    unsigned i;
    float base_x;
    assert(hm_synthetic_room2_init(&room,&combat,tiles,
                                   HM_ROOM2_CELLS)==1);
    assert(hm_session_init(&room,&combat,&game)==HM_SESSION_OK);
    /* A spawn isn't marked grounded until actual native gravity checks. */
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                idle,0u,0u,0u,1.0f/60.0f)==HM_SESSION_OK);
    assert(game.player.grounded==1u);
    assert(dash.remaining==0u && dash.recovery==0u);
    baseline=game;
    base_x=game.player.x;
    /* Fresh ZR speeds up the actual C99 world integration exactly 2x. */
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                right,0u,0u,1u,1.0f/60.0f)==HM_SESSION_OK);
    assert(hm_session_step(&room,&combat,&baseline,right,0u,
                           1.0f/60.0f)==HM_SESSION_OK);
    assert(fabsf((game.player.x-base_x)-4.0f)<0.01f);
    assert(fabsf((baseline.player.x-base_x)-2.0f)<0.01f);
    assert(dash.remaining==11u && dash.recovery==80u);
    /* ZR is an edge, not an autorepeat; active dash cannot restart. */
    for(i=0u;i<5u;++i)
        assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                    right,0u,0u,1u,1.0f/60.0f)==HM_SESSION_OK);
    assert(dash.remaining==6u && dash.recovery==75u);

    before=game;before_dash=dash;
    /* Minus wins over simultaneous ZR and freezes all gameplay ticks. */
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                right,0u,1u,1u,1.0f/60.0f)==HM_SESSION_OK);
    assert(paused==1u && memcmp(&game,&before,sizeof(game))==0);
    assert(memcmp(&dash,&before_dash,sizeof(dash))==0);
    for(i=0u;i<60u;++i) {
        assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                    right,1u,0u,1u,1.0f/60.0f)==HM_SESSION_OK);
        assert(memcmp(&game,&before,sizeof(game))==0);
        assert(memcmp(&dash,&before_dash,sizeof(dash))==0);
    }
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                right,0u,1u,1u,1.0f/60.0f)==HM_SESSION_OK);
    assert(paused==0u && memcmp(&game,&before,sizeof(game))==0);
    assert(memcmp(&dash,&before_dash,sizeof(dash))==0);
    for(i=0u;i<6u;++i)
        assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                    right,0u,0u,0u,1.0f/60.0f)==HM_SESSION_OK);
    assert(dash.remaining==0u && dash.recovery==69u);

    /* Repeated presses during recovery use ordinary world speed. */
    base_x=game.player.x;
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                right,0u,0u,1u,1.0f/60.0f)==HM_SESSION_OK);
    assert(fabsf(game.player.x-base_x-2.0f)<0.01f);
    assert(dash.remaining==0u && dash.recovery==68u);
    for(i=0u;i<68u;++i)
        assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                    idle,0u,0u,0u,1.0f/60.0f)==HM_SESSION_OK);
    assert(dash.recovery==0u);
    /* A second genuine ZR edge after recovery restarts fast movement. */
    base_x=game.player.x;
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                right,0u,0u,1u,1.0f/60.0f)==HM_SESSION_OK);
    assert(fabsf(game.player.x-base_x-4.0f)<0.01f);
    assert(dash.remaining==11u);

    before=game;before_dash=dash;before_paused=paused;
    right.axis=NAN;
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                right,0u,0u,0u,1.0f/60.0f)
           ==HM_SESSION_PHYSICS_ERROR);
    assert(memcmp(&game,&before,sizeof(game))==0 &&
           memcmp(&dash,&before_dash,sizeof(dash))==0 &&
           paused==before_paused);
    right.axis=1.0f;
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                right,0u,0u,2u,1.0f/60.0f)
           ==HM_SESSION_INVALID);
    assert(memcmp(&game,&before,sizeof(game))==0 &&
           memcmp(&dash,&before_dash,sizeof(dash))==0);
    invalid=room;invalid.speed=300.0f;
    assert(hm_dash_session_step(&invalid,&combat,&game,&paused,&dash,
                                right,0u,0u,0u,1.0f/60.0f)
           ==HM_SESSION_PHYSICS_ERROR);
    assert(memcmp(&game,&before,sizeof(game))==0 &&
           memcmp(&dash,&before_dash,sizeof(dash))==0);

    /* B retry cancels active dash and uses the normal native respawn. */
    right.reset=1u;
    assert(hm_dash_session_step(&room,&combat,&game,&paused,&dash,
                                right,0u,0u,0u,1.0f/60.0f)==HM_SESSION_OK);
    assert(dash.remaining==0u);
    assert(game.player.respawns>=1u);
    /* The preceding B-cancellation test deliberately sets reset=1. */
    right.reset=0u;
    /* Airborne ZR cannot initiate a new dash. Jump is driven by the real
       second-room platform physics, not by forging a grounded flag. */
    {
        hm_world air_world,wall_world;
        hm_combat_config air_combat,wall_combat;
        hm_session air_game,wall_game;
        hm_dash_state air_dash={0u,0u},wall_dash={0u,0u};
        hm_input jump_right={1.0f,1u,0u};
        uint8_t air_paused=0u,wall_paused=0u;
        uint8_t air_cells[HM_ROOM2_CELLS],wall_cells[HM_ROOM2_CELLS];
        float airborne_x;
        assert(hm_synthetic_room2_init(&air_world,&air_combat,
                                       air_cells,HM_ROOM2_CELLS)==1);
        assert(hm_session_init(&air_world,&air_combat,&air_game)
               ==HM_SESSION_OK);
        assert(hm_dash_session_step(&air_world,&air_combat,&air_game,
                                    &air_paused,&air_dash,idle,0u,0u,0u,
                                    1.0f/60.0f)==HM_SESSION_OK);
        assert(air_game.player.grounded==1u);
        assert(hm_dash_session_step(&air_world,&air_combat,&air_game,
                                    &air_paused,&air_dash,jump_right,
                                    0u,0u,0u,1.0f/60.0f)==HM_SESSION_OK);
        assert(air_game.player.grounded==0u);
        airborne_x=air_game.player.x;
        assert(hm_dash_session_step(&air_world,&air_combat,&air_game,
                                    &air_paused,&air_dash,right,0u,0u,1u,
                                    1.0f/60.0f)==HM_SESSION_OK);
        assert(air_dash.remaining==0u && air_dash.recovery==0u);
        assert(fabsf(air_game.player.x-airborne_x-2.0f)<0.01f);

        /* A synthetic solid pillar immediately to the right of spawn
           must stop a dash at its left edge despite doubled speed.
           This exercises hm_step's REAL swept collision, not a mock. */
        assert(hm_synthetic_room2_init(&wall_world,&wall_combat,
                                       wall_cells,HM_ROOM2_CELLS)==1);
        wall_cells[17u*HM_ROOM2_COLUMNS+4u]=1u;
        assert(hm_session_init(&wall_world,&wall_combat,&wall_game)
               ==HM_SESSION_OK);
        assert(hm_dash_session_step(&wall_world,&wall_combat,&wall_game,
                                    &wall_paused,&wall_dash,idle,0u,0u,0u,
                                    1.0f/60.0f)==HM_SESSION_OK);
        assert(wall_game.player.grounded==1u);
        for(i=0u;i<8u;++i)
            assert(hm_dash_session_step(&wall_world,&wall_combat,&wall_game,
                                        &wall_paused,&wall_dash,right,0u,0u,
                                        (uint8_t)(i==0u),1.0f/60.0f)
                   ==HM_SESSION_OK);
        assert(wall_game.player.x>50.0f);
        assert(wall_game.player.x<=59.01f);
        assert(wall_game.player.wall_hit==1u);
        assert(wall_dash.remaining==4u && wall_dash.recovery==73u);
    }

    puts("PASS: actual second-room ZR dash, 60Hz, cooldown, Minus freeze, rollback");
    return 0;
}
