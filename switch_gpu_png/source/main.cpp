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

// Stage228: the input and the offscreen output are invented 16x8 RGBA8 data.
// An NRO cross-build is not evidence of an actual GPU draw or readback.
struct Stage228Vertex { float x, y, u, v; };
static constexpr Stage228Vertex kQuad[4] = {
    {-1.0f,  1.0f, 0.0f, 0.0f},
    {-1.0f, -1.0f, 0.0f, 1.0f},
    { 1.0f,  1.0f, 1.0f, 0.0f},
    { 1.0f, -1.0f, 1.0f, 1.0f}
};

static bool loadStage228Shader(dk::MemBlock codeMem, uint32_t offset,
                              const char* name, DkStage stage, dk::Shader& shader)
{
    FILE* file=std::fopen(name,"rb");
    if(!file) return false;
    bool ok=std::fseek(file,0,SEEK_END)==0;
    const long length=ok?std::ftell(file):-1;
    ok=length>=static_cast<long>(sizeof(Stage227Header)) && length<=2048 &&
       std::fseek(file,0,SEEK_SET)==0;
    if(ok) {
        auto* dst=static_cast<uint8_t*>(codeMem.getCpuAddr());
        ok=dst && std::fread(dst+offset,1u,(size_t)length,file)==(size_t)length;
    }
    std::fclose(file);
    if(!ok) return false;
    dk::ShaderMaker{codeMem,offset}.initialize(shader);
    return shader.isValid() && shader.getStage()==stage;
}

static int runStage228Draw(dk::Device device, dk::Queue queue,
                           dk::Image const& texture,
                           dk::ImageDescriptor const& imageDesc,
                           dk::SamplerDescriptor const& samplerDesc,
                           dk::Shader const& vertexShader,
                           dk::Shader const& fragmentShader)
{
    // Separate resources: the readback must come from the render target,
    // never from the source staging buffer or an invented CPU-side "GPU" result.
    dk::ImageLayout outputLayout;
    dk::ImageLayoutMaker{device}.setFlags(DkImageFlags_UsageRender)
        .setFormat(DkImageFormat_RGBA8_Unorm)
        .setDimensions(kWidth,kHeight).initialize(outputLayout);
    const uint64_t outputAlignment=outputLayout.getAlignment();
    if(outputAlignment==0 || (outputAlignment&(outputAlignment-1u))!=0 ||
       outputAlignment>0x100000u || outputLayout.getSize()>0x100000u)
        return 20;
    const uint64_t blockAlignment=outputAlignment>DK_MEMBLOCK_ALIGNMENT
        ?outputAlignment:DK_MEMBLOCK_ALIGNMENT;
    const uint64_t outputBytes=(outputLayout.getSize()+blockAlignment-1u)
                              & ~(blockAlignment-1u);
    if(outputBytes==0 || outputBytes>0x100000u) return 21;
    auto outputMem=dk::MemBlockMaker{device,(uint32_t)outputBytes}
        .setFlags(DkMemBlockFlags_GpuCached|DkMemBlockFlags_Image).create();
    if(!outputMem) return 22;
    dk::Image outputImage;
    outputImage.initialize(outputLayout,outputMem,0u);
    dk::ImageView outputView{outputImage};

    auto descriptorMem=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    auto samplerMem=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    auto vertexMem=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    auto readbackMem=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    auto drawCommandMem=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT*2u}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    if(!descriptorMem||!samplerMem||!vertexMem||!readbackMem||!drawCommandMem ||
       !descriptorMem.getCpuAddr()||!samplerMem.getCpuAddr()||
       !vertexMem.getCpuAddr()||!readbackMem.getCpuAddr()) return 23;
    std::memcpy(descriptorMem.getCpuAddr(),&imageDesc,sizeof imageDesc);
    std::memcpy(samplerMem.getCpuAddr(),&samplerDesc,sizeof samplerDesc);
    std::memcpy(vertexMem.getCpuAddr(),kQuad,sizeof kQuad);
    std::memset(readbackMem.getCpuAddr(),0xa5,kGpuUploadBytes);

    auto cmd=dk::CmdBufMaker{device}.create();
    if(!cmd) return 24;
    cmd.addMemory(drawCommandMem,0u,DK_MEMBLOCK_ALIGNMENT*2u);
    cmd.bindImageDescriptorSet(descriptorMem.getGpuAddr(),1u);
    cmd.bindSamplerDescriptorSet(samplerMem.getGpuAddr(),1u);
    cmd.barrier(DkBarrier_None,DkInvalidateFlags_Descriptors|DkInvalidateFlags_Shader);
    cmd.bindShaders(DkStageFlag_GraphicsMask,{&vertexShader,&fragmentShader});
    cmd.bindRenderTargets({&outputView});
    cmd.setViewports(0,DkViewport{0.0f,0.0f,(float)kWidth,(float)kHeight,0.0f,1.0f});
    cmd.setScissors(0,DkScissor{0u,0u,kWidth,kHeight});
    cmd.bindRasterizerState(dk::RasterizerState{}.setCullMode(DkFace_None));
    cmd.bindColorState(dk::ColorState{});
    cmd.bindColorWriteState(dk::ColorWriteState{});
    cmd.bindDepthStencilState(dk::DepthStencilState{}.setDepthTestEnable(false));
    const DkVtxAttribState attribs[2] = {
        {0,0,0,DkVtxAttribSize_2x32,DkVtxAttribType_Float,0},
        {0,0,8,DkVtxAttribSize_2x32,DkVtxAttribType_Float,0}
    };
    const DkVtxBufferState buffers[1] = {{sizeof(Stage228Vertex),0}};
    cmd.bindVtxAttribState(attribs);
    cmd.bindVtxBufferState(buffers);
    cmd.bindVtxBuffer(0,vertexMem.getGpuAddr(),sizeof kQuad);
    cmd.bindTextures(DkStage_Fragment,0,dkMakeTextureHandle(0,0));
    cmd.draw(DkPrimitive_TriangleStrip,4,1,0,0);
    cmd.barrier(DkBarrier_Full,DkInvalidateFlags_Image);
    cmd.copyImageToBuffer(outputView,{0u,0u,0u,kWidth,kHeight,1u},
                          {readbackMem.getGpuAddr(),0u,0u});
    queue.submitCommands(cmd.finishList());
    queue.waitIdle();
    const auto* pixels=static_cast<const uint8_t*>(readbackMem.getCpuAddr());
    uint32_t mismatches=0;
    for(uint32_t y=0;y<kHeight;++y) for(uint32_t x=0;x<kWidth;++x) {
        const auto p=(y*kWidth+x)*4u;
        if(std::memcmp(pixels+p,s_padded+p,4u)!=0) {
            if(mismatches<8u)
                std::printf("STAGE228_PIXEL_MISMATCH x=%u y=%u expected=%02x%02x%02x%02x got=%02x%02x%02x%02x\n",
                            x,y,s_padded[p],s_padded[p+1],s_padded[p+2],s_padded[p+3],
                            pixels[p],pixels[p+1],pixels[p+2],pixels[p+3]);
            ++mismatches;
        }
    }
    std::printf("STAGE228_GPU_QUAD_READBACK pixels=%u mismatches=%u\n",
                kWidth*kHeight,mismatches);
    (void)texture; // texture lifetime is owned by the caller through queue.waitIdle().
    return mismatches==0?0:25;
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
    if(!shadersReady) { romfsExit(); return 12; }
    // Unlike Stage225's libnx software framebuffer this creates an actual
    // Tegra image, stages CPU-generated pixels and submits a GPU copy command.
    auto device = dk::DeviceMaker{}.create();
    if(!device) return 3;
    auto queue = dk::QueueMaker{device}.setFlags(DkQueueFlags_Graphics).create();
    if(!queue) return 4;

    // Load the exact packaged DKSH programs into GPU code memory.
    // The DKSH control section is included in each slot, as in deko3d examples.
    auto shaderMem=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT*4u}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached|
                  DkMemBlockFlags_Code).create();
    if(!shaderMem||!shaderMem.getCpuAddr()) {romfsExit(); return 13;}
    dk::Shader vertexShader{},fragmentShader{};
    const bool loaded=
        loadStage228Shader(shaderMem,0u,
            "romfs:/shaders/padded_texture_vsh.dksh",DkStage_Vertex,vertexShader) &&
        loadStage228Shader(shaderMem,DK_MEMBLOCK_ALIGNMENT,
            "romfs:/shaders/padded_texture_fsh.dksh",DkStage_Fragment,fragmentShader);
    romfsExit();
    if(!loaded) return 14;

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
    // Stage228 renders an offscreen textured quad, then reads back *that*
    // render target. Cross-building this command path proves no execution.
    return runStage228Draw(device,queue,image,imageDescriptor,samplerDescriptor,
                           vertexShader,fragmentShader);
}
