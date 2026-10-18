#include "heman_mask.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static uint16_t ids[4]={1,2,UINT16_MAX,UINT16_MAX};
static uint64_t masks[3*16];
static hm_mask_grid fixture(void) {
    hm_mask_grid g={ids,masks,2,2,16,3};
    unsigned row;
    for(row=0;row<16;++row) {
        masks[row]=0;
        masks[16+row]=(UINT64_C(1) << (row+1))-1;
        masks[32+row]=UINT64_C(65535);
    }
    return g;
}
int main(void) {
    hm_mask_grid g=fixture(); int32_t contact=123;
    assert(hm_mask_valid(&g));
    assert(hm_mask_solid_at(&g,0,0)==1);
    assert(hm_mask_solid_at(&g,15,0)==0);
    assert(hm_mask_solid_at(&g,17,0)==1);
    assert(hm_mask_solid_at(&g,17,-1)==0);
    assert(hm_mask_body_overlap(&g,23,0,1,1)==0);
    assert(hm_mask_body_overlap(&g,23,2,1,1)==1);
    assert(hm_mask_feet_contact(&g,0,0,0,15,&contact)==1 && contact==0);
    assert(hm_mask_feet_contact(&g,15,0,0,15,&contact)==1 && contact==15);
    assert(hm_mask_feet_contact(&g,0,0,-25,-20,&contact)==0);
    assert(hm_mask_feet_contact(&g,0,0,0,600,&contact)==-1);
    ids[0]=999;
    assert(!hm_mask_valid(&g));
    ids[0]=1;
    masks[16]=UINT64_C(1)<<17;
    assert(!hm_mask_valid(&g));
    puts("PASS: synthetic C99 pixel masks and slope contact");
    return 0;
}
