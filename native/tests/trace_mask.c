/* CSV geometry trace on synthetic packed slope and flat masks. */
#include "heman_mask.h"
#include <stdint.h>
#include <stdio.h>
static const uint16_t ids[4]={1,2,UINT16_MAX,UINT16_MAX};
static uint64_t masks[3*16];
int main(void) {
    hm_mask_grid grid={ids,masks,2,2,16,3};
    int x, y;
    unsigned row;
    for(row=0;row<16;++row) {
        masks[row]=0;
        masks[16+row]=(UINT64_C(1)<<(row+1))-1;
        masks[32+row]=UINT64_C(65535);
    }
    if(!hm_mask_valid(&grid))return 2;
    puts("x,found,contact_y,solid_y0,body_overlap");
    for(x=0;x<32;++x) {
        y=-1;
        {
            const int result=hm_mask_feet_contact(&grid,(float)x,0.0f,0.0f,15.0f,&y);
            const int solid=hm_mask_solid_at(&grid,x,0);
            const int overlap=hm_mask_body_overlap(&grid,(float)x,4.0f,1.0f,4.0f);
            if(result<0||solid<0||overlap<0)return 3;
            printf("%d,%d,%d,%d,%d\n",x,result,y,solid,overlap);
        }
    }
    return 0;
}
