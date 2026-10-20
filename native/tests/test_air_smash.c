/* Real synthetic C99 physics+combat aerial strike; no source-game data. */
#include "heman_air_smash.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define NC 24u
#define NR 20u
static uint8_t cells[NC*NR];
static const hm_event far_exit[]={{HM_EXIT, 260.0f, 224.0f, 9.0f}};
static hm_world make_world(void) {
    hm_world w;
    unsigned x;
    memset(&w,0,sizeof(w)); memset(cells,0,sizeof(cells));
    for(x=0u;x<NC;++x)cells[14u*NC+x]=1u;
    w.solid=cells;w.columns=NC;w.rows=NR;w.tile_size=16u;
    w.spawn_x=32.0f;w.spawn_feet_y=224.0f;
    w.actor_half_width=5.0f;w.actor_height=22.0f;
    w.speed=120.0f;w.gravity=1200.0f;w.jump_speed=420.0f;
    w.terminal_speed=1400.0f;w.viewport_width=320.0f;
    w.viewport_height=240.0f;w.death_margin=96.0f;
    w.events=far_exit;w.event_count=1u;
    return w;
}
static hm_combat_config make_combat(void) {
    hm_combat_config c;
    memset(&c,0,sizeof(c));
    c.patrol_left=40.0f;c.patrol_right=48.0f;
    c.enemy_start_x=40.0f;c.enemy_feet_y=224.0f;
    c.enemy_speed=8.0f;c.sword_reach=28.0f;
    c.contact_range=5.0f;c.enemy_initial_hp=2u;
    c.player_initial_hp=3u;c.sword_cooldown_frames=12u;
    c.hurt_cooldown_frames=45u;
    return c;
}
static hm_session_result step(const hm_world *w, const hm_combat_config *c,
        hm_session *s,uint8_t *p,hm_dash_state *d,hm_air_smash_state *a,
        hm_input in,uint8_t minus,uint8_t zl,uint8_t stage) {
    return hm_air_smash_step(w,c,s,p,d,a,stage,in,0u,minus,0u,zl,1.0f/60.0f);
}
int main(void) {
    hm_world w=make_world(), bad;
    hm_combat_config c=make_combat();
    hm_session s,snapshot;
    hm_dash_state dash={0u,0u},d_old;
    hm_air_smash_state ability={0},a_old;
    hm_input idle={0.0f,0u,0u},jump={0.0f,1u,0u},retry={0.0f,0u,1u};
    uint8_t paused=0u,old_pause;
    unsigned i;
    assert(hm_session_init(&w,&c,&s)==HM_SESSION_OK);
    assert(step(&w,&c,&s,&paused,&dash,&ability,idle,0u,0u,1u)==HM_SESSION_OK);
    assert(s.player.grounded==1u);
    /* Pressing ZL while grounded must not arm or bypass normal combat. */
    assert(step(&w,&c,&s,&paused,&dash,&ability,idle,0u,1u,1u)==HM_SESSION_OK);
    assert(ability.armed==0u && ability.impacts==0u);
    assert(step(&w,&c,&s,&paused,&dash,&ability,jump,0u,0u,1u)==HM_SESSION_OK);
    assert(s.player.grounded==0u && s.player.vy<0.0f);
    /* Minus and simultaneous ZL have priority: no attack, no physics. */
    snapshot=s;d_old=dash;a_old=ability;
    assert(step(&w,&c,&s,&paused,&dash,&ability,idle,1u,1u,1u)==HM_SESSION_OK);
    assert(paused==1u && memcmp(&snapshot,&s,sizeof(s))==0);
    assert(memcmp(&ability,&a_old,sizeof(a_old))==0);
    assert(step(&w,&c,&s,&paused,&dash,&ability,idle,0u,1u,1u)==HM_SESSION_OK);
    assert(paused==1u && memcmp(&snapshot,&s,sizeof(s))==0);
    assert(step(&w,&c,&s,&paused,&dash,&ability,idle,1u,1u,1u)==HM_SESSION_OK);
    assert(paused==0u && memcmp(&snapshot,&s,sizeof(s))==0);

    /* One legitimate airborne ZL drives native swept fall into landing. */
    for(i=0u;i<30u && ability.impacts==0u;++i)
        assert(step(&w,&c,&s,&paused,&dash,&ability,idle,0u,
                    (uint8_t)(i==0u),1u)==HM_SESSION_OK);
    assert(ability.impacts==1u && ability.enemy_hits==1u);
    assert(ability.armed==0u && s.player.grounded==1u);
    assert(ability.impact_frames==HM_SMASH_FEEDBACK_FRAMES);
    assert(s.combat.enemy_hp==1u);
    assert(ability.cooldown>0u);
    /* A second ZL cannot repeat an existing landing or bypass recovery. */
    for(i=0u;i<12u;++i)
        assert(step(&w,&c,&s,&paused,&dash,&ability,idle,0u,1u,1u)==HM_SESSION_OK);
    assert(ability.impacts==1u && ability.enemy_hits==1u);
    assert(ability.impact_frames==0u && ability.cooldown>0u);

    /* Native B respawn is not an air strike; it must clear active attack. */
    assert(step(&w,&c,&s,&paused,&dash,&ability,jump,0u,0u,1u)==HM_SESSION_OK);
    /* Existing cooldown cannot be bypassed by ZL. */
    assert(step(&w,&c,&s,&paused,&dash,&ability,idle,0u,1u,1u)==HM_SESSION_OK);
    assert(ability.impacts==1u);
    assert(step(&w,&c,&s,&paused,&dash,&ability,retry,0u,0u,1u)==HM_SESSION_OK);
    assert(ability.armed==0u && ability.cooldown==0u);
    assert(s.player.respawns>0u);

    /* Failure must be byte-for-byte atomic, even with unfinished attack. */
    snapshot=s;d_old=dash;a_old=ability;old_pause=paused;
    {
        hm_input bad_input={NAN,0u,0u};
        assert(step(&w,&c,&s,&paused,&dash,&ability,bad_input,0u,0u,1u)
               ==HM_SESSION_PHYSICS_ERROR);
    }
    assert(memcmp(&s,&snapshot,sizeof(s))==0 &&
           memcmp(&dash,&d_old,sizeof(dash))==0 &&
           memcmp(&ability,&a_old,sizeof(ability))==0 && paused==old_pause);
    assert(step(&w,&c,&s,&paused,&dash,&ability,idle,0u,2u,1u)
           ==HM_SESSION_INVALID);
    bad=w;bad.columns=0u;
    assert(step(&bad,&c,&s,&paused,&dash,&ability,idle,0u,0u,1u)
           !=HM_SESSION_OK);
    assert(memcmp(&s,&snapshot,sizeof(s))==0 &&
           memcmp(&ability,&a_old,sizeof(ability))==0);

    /* Native final B runs a fresh room session and resets the skill. */
    s.player.completed=1u;
    ability.impacts=3u;ability.enemy_hits=1u;ability.cooldown=3u;
    assert(step(&w,&c,&s,&paused,&dash,&ability,retry,0u,0u,1u)==HM_SESSION_OK);
    assert(s.player.completed==0u && s.player.frame==0u);
    assert(ability.impacts==0u && ability.enemy_hits==0u);
    assert(ability.cooldown==0u && ability.impact_frames==0u);

    /* Stage 1-only skill; in stage 0 ZL is ignored by normal adapter. */
    assert(hm_session_init(&w,&c,&s)==HM_SESSION_OK);
    assert(step(&w,&c,&s,&paused,&dash,&ability,idle,0u,1u,0u)==HM_SESSION_OK);
    assert(ability.impacts==0u && ability.armed==0u);
    puts("PASS: native airborne ZL smash, one landing hit, pause, cooldown, atomic retry");
    return 0;
}
