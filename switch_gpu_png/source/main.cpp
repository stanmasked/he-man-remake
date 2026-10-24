/* Stage226: asset-free GPU image transfer smoke via deko3d.
 * This program proves nothing about read-back, shader sampling or iOS parity.
 * A successful *run* would at most confirm a real deko3d image upload.
 */
#include <switch.h>
#include <deko3d.hpp>
#include <cstdint>
#include <cstring>
#include <cstdio>

extern "C" {
#include "heman_native_png_upload.h"
}

static constexpr uint32_t kPngWidth=9, kPngHeight=5;
static constexpr uint32_t kWidth=16, kHeight=8;
static constexpr uint32_t kGpuUploadBytes=kWidth*kHeight*4u;
static uint8_t s_original[kPngWidth*kPngHeight*4u];
static uint8_t s_padded[kGpuUploadBytes];

static bool buildSyntheticSource()
{
    for (uint32_t y=0; y<kPngHeight; ++y) {
        for(uint32_t x=0; x<kPngWidth; ++x) {
            const uint32_t p=(y*kPngWidth+x)*4u;
            s_original[p+0]=(uint8_t)(x*20u);
            s_original[p+1]=(uint8_t)(y*30u);
            s_original[p+2]=(uint8_t)(x+y);
            s_original[p+3]=255u;
        }
    }
    hm_texture_reference_binding binding{};
    if (hm_native_png_prepare_rgba(s_original,sizeof s_original,
            kPngWidth,kPngHeight,0,0,0,0,0,
            s_padded,sizeof s_padded,&binding)!=HM_NATIVE_PNG_UPLOAD_OK)
        return false;
    if(binding.width!=kWidth||binding.height!=kHeight||
       binding.rgba_size!=kGpuUploadBytes) return false;
    for(uint32_t y=0;y<kHeight;++y) for(uint32_t x=0;x<kWidth;++x) {
        const uint32_t offset=(y*kWidth+x)*4u;
        if (x>=kPngWidth || y>=kPngHeight) {
            if (s_padded[offset]!=0 || s_padded[offset+1]!=0 ||
                s_padded[offset+2]!=0 || s_padded[offset+3]!=255) return false;
        }
    }
    return true;
}

// Stage227 verifies both DKSH resources in the *installed NRO's RomFS*.
// This does NOT bind GPU shaders or prove fragment sampling.
struct Stage227Header {
    uint32_t magic, headerSize, controlSize, codeSize, programsOffset, programs;
};
static bool verifyPackagedShader(const char* name)
{
    FILE* file=std::fopen(name,"rb");
    if(!file) return false;
    Stage227Header header{};
    bool valid=std::fread(&header,sizeof header,1u,file)==1u;
    if(valid) {
        valid=(header.magic==0x48534b44u && header.headerSize>=sizeof header &&
               header.controlSize>=header.headerSize &&
               header.controlSize<=1024u*1024u &&
               header.codeSize>0 && header.codeSize<=1024u*1024u &&
               header.programsOffset>=header.headerSize &&
               header.programsOffset<header.controlSize &&
               header.programs>=1u && header.programs<=16u);
        if(valid && std::fseek(file,0,SEEK_END)==0) {
            long end=std::ftell(file);
            valid=end>=0 && (uint64_t)end >=
                (uint64_t)header.controlSize+(uint64_t)header.codeSize;
        } else valid=false;
    }
    std::fclose(file);
    return valid;
}

int main(int argc, char** argv)
{
    (void)argc; (void)argv;
    if(!buildSyntheticSource()) return 2;
    const Result romfsResult=romfsInit();
    if(R_FAILED(romfsResult)) return 11;
    const bool shadersReady=
        verifyPackagedShader("romfs:/shaders/padded_texture_vsh.dksh") &&
        verifyPackagedShader("romfs:/shaders/padded_texture_fsh.dksh");
    romfsExit();
    if(!shadersReady) return 12;
    // Unlike Stage225's libnx software framebuffer this creates an actual
    // Tegra image, stages CPU-generated pixels and submits a GPU copy command.
    auto device = dk::DeviceMaker{}.create();
    if(!device) return 3;
    auto queue = dk::QueueMaker{device}.setFlags(DkQueueFlags_Graphics).create();
    if(!queue) return 4;
    dk::ImageLayout layout;
    dk::ImageLayoutMaker{device}.setFormat(DkImageFormat_RGBA8_Unorm)
        .setDimensions(kWidth,kHeight).initialize(layout);

    const uint32_t imageAlignment=layout.getAlignment();
    if(imageAlignment==0 || (imageAlignment&(imageAlignment-1u))!=0 ||
       imageAlignment>0x100000u) return 5;
    const uint32_t allocationAlignment=
        imageAlignment>DK_MEMBLOCK_ALIGNMENT?imageAlignment:DK_MEMBLOCK_ALIGNMENT;
    const uint32_t imageBytes=(layout.getSize()+allocationAlignment-1u)
        & ~(allocationAlignment-1u);
    if(imageBytes==0 || imageBytes>0x100000u) return 6;

    auto imageMem=dk::MemBlockMaker{device,imageBytes}
        .setFlags(DkMemBlockFlags_GpuCached|DkMemBlockFlags_Image).create();
    if(!imageMem) return 7;
    dk::Image image;
    image.initialize(layout,imageMem,0u);
    dk::ImageDescriptor imageDescriptor;
    imageDescriptor.initialize(image);

    auto staging=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    if(!staging || !staging.getCpuAddr()) return 8;
    std::memcpy(staging.getCpuAddr(),s_padded,sizeof s_padded);

    auto cmdmem=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    if(!cmdmem) return 9;
    auto cmds=dk::CmdBufMaker{device}.create();
    if(!cmds) return 10;
    cmds.addMemory(cmdmem,0u,DK_MEMBLOCK_ALIGNMENT);
    dk::ImageView view{image};
    cmds.copyBufferToImage({staging.getGpuAddr(),0u,0u},view,{0,0,0,kWidth,kHeight,1});
    queue.submitCommands(cmds.finishList());
    queue.waitIdle();

    dk::Sampler sampler;
    sampler.setFilter(DkFilter_Nearest,DkFilter_Nearest);
    sampler.setWrapMode(DkWrapMode_ClampToEdge,
                        DkWrapMode_ClampToEdge,DkWrapMode_ClampToEdge);
    dk::SamplerDescriptor samplerDescriptor;
    samplerDescriptor.initialize(sampler);
    // Descriptor construction is not shader binding or sampled-pixel proof.
    return 0;
}
