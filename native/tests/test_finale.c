/* Asset-free terminal room-2 native gameplay regression. */
#include "heman_finale.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define C 24u
#define R 20u
static uint8_t tiles[C*R];
static const hm_event trigger[] = {{HM_EXIT, 32.0f, 224.0f, 9.0f}};
static hm_world world_fixture(void) {
    hm_world w;
    unsigned i;
    memset(&w,0,sizeof(w));
    memset(tiles,0,sizeof(tiles));
    for(i=0u;i<C;++i)tiles[14u*C+i]=1u;
    w.solid=tiles;w.columns=C;w.rows=R;w.tile_size=16u;
    w.spawn_x=32.0f;w.spawn_feet_y=224.0f;
    w.actor_half_width=5.0f;w.actor_height=22.0f;
    w.speed=120.0f;w.gravity=1200.0f;w.jump_speed=420.0f;
    w.terminal_speed=1400.0f;w.viewport_width=320.0f;
    w.viewport_height=240.0f;w.death_margin=96.0f;
    w.events=trigger;w.event_count=1u;
    return w;
}
static hm_combat_config combat_fixture(void) {
    hm_combat_config c;
    memset(&c,0,sizeof(c));
    c.patrol_left=100.0f;c.patrol_right=180.0f;
    c.enemy_start_x=140.0f;c.enemy_feet_y=224.0f;
    c.enemy_speed=30.0f;c.sword_reach=30.0f;
    c.contact_range=8.0f;c.enemy_initial_hp=2u;
    c.player_initial_hp=3u;c.sword_cooldown_frames=12u;
    c.hurt_cooldown_frames=30u;
    return c;
}
static hm_session_result tick(const hm_world *w,const hm_combat_config *c,
   hm_session *s,uint8_t *paused,hm_dash_state *dash,uint8_t stage,
   hm_input input,uint8_t attack,uint8_t toggle,uint8_t boost) {
    return hm_finale_session_step(w,c,s,paused,dash,stage,input,
                                  attack,toggle,boost,1.0f/60.0f);
}
int main(void) {
    hm_world w=world_fixture(),invalid;
    hm_combat_config c=combat_fixture();
    hm_session game,snap;
    hm_dash_state dash={0u,0u},old_dash;
    hm_input still={0.0f,0u,0u},right={1.0f,0u,0u},
             retry={0.0f,0u,1u};
    uint8_t paused=0u,old_pause;
    unsigned i;
    assert(hm_session_init(&w,&c,&game)==HM_SESSION_OK);
    /* Exit must be earned by the actual C99 event engine, not faked. */
    assert(tick(&w,&c,&game,&paused,&dash,1u,still,0u,0u,0u)
           ==HM_SESSION_OK);
    assert(game.player.frame==1u);
    assert(game.player.completed==1u);
    snap=game;
    dash.remaining=7u;dash.recovery=40u;old_dash=dash;
    /* Finale must preserve all physics/combat/cooldowns, including dash. */
    for(i=0u;i<90u;++i) {
        assert(tick(&w,&c,&game,&paused,&dash,1u,right,1u,0u,1u)
               ==HM_SESSION_OK);
        assert(memcmp(&game,&snap,sizeof(game))==0);
        assert(memcmp(&dash,&old_dash,sizeof(dash))==0);
    }
    /* Pause has priority over other buttons; toggling does not tick. */
    assert(tick(&w,&c,&game,&paused,&dash,1u,retry,1u,1u,1u)
           ==HM_SESSION_OK);
    assert(paused==1u);
    assert(memcmp(&game,&snap,sizeof(game))==0);
    assert(tick(&w,&c,&game,&paused,&dash,1u,retry,1u,0u,1u)
           ==HM_SESSION_OK);
    assert(paused==1u && memcmp(&game,&snap,sizeof(game))==0);
    assert(tick(&w,&c,&game,&paused,&dash,1u,right,0u,1u,0u)
           ==HM_SESSION_OK);
    assert(paused==0u && memcmp(&game,&snap,sizeof(game))==0);

    /* Even on terminal freeze, malformed commands never look successful. */
    {
        hm_input bad={NAN,0u,0u};
        assert(tick(&w,&c,&game,&paused,&dash,1u,bad,0u,0u,0u)
               ==HM_SESSION_PHYSICS_ERROR);
        assert(memcmp(&game,&snap,sizeof(game))==0);
    }
    assert(tick(&w,&c,&game,&paused,&dash,1u,retry,0u,0u,0u)
           ==HM_SESSION_OK);
    assert(game.player.completed==0u && game.player.frame==0u);
    assert(dash.remaining==0u && dash.recovery==0u);
    assert(game.combat.player_hp==c.player_initial_hp);
    /* Uncompleted simulation resumes after intentional restart. */
    assert(tick(&w,&c,&game,&paused,&dash,1u,still,0u,0u,0u)
           ==HM_SESSION_OK);
    assert(game.player.frame==1u && game.player.completed==1u);

    /* Rollback: a malformed world must not reset a completed session. */
    snap=game;old_dash=dash;old_pause=paused;
    invalid=w;invalid.columns=0u;
    assert(tick(&invalid,&c,&game,&paused,&dash,1u,retry,0u,0u,0u)
           !=HM_SESSION_OK);
    assert(memcmp(&game,&snap,sizeof(game))==0);
    assert(memcmp(&dash,&old_dash,sizeof(dash))==0 && paused==old_pause);

    /* Stage 0 is still ordinary native pause/session, not a final screen. */
    assert(hm_session_init(&w,&c,&game)==HM_SESSION_OK);
    assert(tick(&w,&c,&game,&paused,&dash,0u,still,0u,0u,0u)
           ==HM_SESSION_OK);
    assert(game.player.frame==1u);
    /* Invalid stages and booleans are rejected with atomic rollback. */
    snap=game;old_dash=dash;
    assert(tick(&w,&c,&game,&paused,&dash,2u,still,0u,0u,0u)
           ==HM_SESSION_INVALID);
    assert(tick(&w,&c,&game,&paused,&dash,1u,still,0u,0u,2u)
           ==HM_SESSION_INVALID);
    assert(memcmp(&game,&snap,sizeof(game))==0);
    assert(memcmp(&dash,&old_dash,sizeof(dash))==0);
    puts("PASS: actual C99 exit earns final freeze; B restarts; pause, invalids, dash atomic");
    return 0;
}
