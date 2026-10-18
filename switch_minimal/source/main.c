/* An isolated libnx guest diagnostic. NO He-Man game code is linked.
   If this never appears in the emulator, troubleshoot the runtime/loader
   before attributing failures to the actual gameplay or raster engine. */
#include <switch.h>
#include <stdint.h>
#include <string.h>

#define W 640u
#define H 360u

int main(int argc, char **argv) {
    Framebuffer fb;
    Result rc;
    PadState pad;
    int marker_x = 100;
    (void)argc; (void)argv;
    memset(&fb,0,sizeof(fb));
    padConfigureInput(1,HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);
    rc=framebufferCreate(&fb,nwindowGetDefault(),W,H,
                         PIXEL_FORMAT_RGBA_8888,2);
    if(R_FAILED(rc))return 2;
    rc=framebufferMakeLinear(&fb);
    if(R_FAILED(rc)){framebufferClose(&fb);return 3;}
    while(appletMainLoop()) {
        uint32_t row,col,stride=0u;
        uint32_t *pixels;
        uint64_t held;
        padUpdate(&pad);
        held=padGetButtons(&pad);
        if(padGetButtonsDown(&pad)&HidNpadButton_Plus)break;
        if((held&HidNpadButton_Right) && marker_x<410)marker_x+=2;
        if((held&HidNpadButton_Left) && marker_x>20)marker_x-=2;
        pixels=(uint32_t*)framebufferBegin(&fb,&stride);
        if(!pixels || stride%sizeof(uint32_t)!=0u)break;
        stride/=sizeof(uint32_t);
        if(stride<W){framebufferEnd(&fb);break;}
        for(row=0u;row<H;++row)
            for(col=0u;col<W;++col) {
                uint32_t color=UINT32_C(0xff202f47);
                if(row>=60u && row<300u && col>=20u && col<620u)
                    color=((col/40u+row/40u)&1u) ?
                        UINT32_C(0xff477f6b):UINT32_C(0xff386080);
                /* Solid guest-only magenta rectangle: 110x100 pixels,
                   positioned by exactly one input-driven integer. */
                if(row>=105u && row<205u &&
                   col>=(uint32_t)marker_x &&
                   col<(uint32_t)(marker_x+110))
                    color=UINT32_C(0xffff00ff);
                pixels[row*stride+col]=color;
            }
        framebufferEnd(&fb);
        svcSleepThread(16666667LL);
    }
    framebufferClose(&fb);
    return 0;
}
