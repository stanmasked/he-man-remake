/* Stage226: asset-free GPU image transfer smoke via deko3d.
 * This program proves nothing about read-back, shader sampling or iOS parity.
 * A successful *run* would at most confirm a real deko3d image upload.
 */
#include <switch.h>
#include <deko3d.hpp>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cerrno>
#include <sys/stat.h>

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
// Stage232: verify the exact one-program DKSH layout before handing it to
// deko3d. The SDK expects a complete 64-byte DkshProgramHeader inside the
// 256-aligned control section, followed by aligned GPU machine code.
static bool verifyPackagedShader(const char* name, DkStage stage)
{
    FILE* file=std::fopen(name,"rb");
    if(!file) return false;
    Stage227Header header{};
    bool valid=std::fread(&header,sizeof header,1u,file)==1u;
    if(valid) {
        const bool vertex=stage==DkStage_Vertex;
        const bool fragment=stage==DkStage_Fragment;
        valid=(vertex||fragment) &&
            header.magic==0x48534b44u &&
            header.headerSize==sizeof(Stage227Header) &&
            header.controlSize>=header.headerSize+64u &&
            header.controlSize<=4096u &&
            (header.controlSize%DK_SHADER_CODE_ALIGNMENT)==0 &&
            header.codeSize>=DK_SHADER_CODE_ALIGNMENT &&
            header.codeSize<=4096u &&
            (header.codeSize%DK_SHADER_CODE_ALIGNMENT)==0 &&
            header.programs==1u &&
            header.programsOffset>=header.headerSize &&
            (uint64_t)header.programsOffset+64u<=header.controlSize;
        if(valid) {
            uint32_t actualType=UINT32_MAX;
            valid=std::fseek(file,(long)header.programsOffset,SEEK_SET)==0 &&
                std::fread(&actualType,sizeof actualType,1u,file)==1u &&
                actualType==(vertex?0u:1u);
        }
        if(valid) {
            valid=std::fseek(file,0,SEEK_END)==0;
            const long size=valid?std::ftell(file):-1;
            valid=size>=0 && (uint64_t)size==
                (uint64_t)header.controlSize+(uint64_t)header.codeSize;
        }
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
    if(!verifyPackagedShader(name,stage) ||
       (offset%DK_SHADER_CODE_ALIGNMENT)!=0) return false;
    FILE* file=std::fopen(name,"rb");
    if(!file) return false;
    Stage227Header header{};
    bool ok=std::fread(&header,sizeof header,1u,file)==1u;
    const uint64_t length=(uint64_t)header.controlSize+header.codeSize;
    // The last DK_SHADER_CODE_UNUSABLE_SIZE bytes of every code MemBlock
    // are reserved by deko3d. Reject overlaps even when CPU memcpy fits.
    const uint64_t cap=codeMem.getSize();
    ok=ok && cap>=DK_SHADER_CODE_UNUSABLE_SIZE &&
       (uint64_t)offset+length<=cap-DK_SHADER_CODE_UNUSABLE_SIZE &&
       length>0 && length<=8192u &&
       std::fseek(file,0,SEEK_SET)==0;
    if(ok) {
        auto* dst=static_cast<uint8_t*>(codeMem.getCpuAddr());
        ok=dst && std::fread(dst+offset,1u,(size_t)length,file)==(size_t)length;
    }
    std::fclose(file);
    if(!ok) return false;
    // The deko3d SDK explicitly supports the inline control+code form.
    dk::ShaderMaker{codeMem,offset}.setProgramId(0u).initialize(shader);
    return shader.isValid() && shader.getStage()==stage;
}

// Stage231 host-generated 128-bit challenge binds the SD result to an
// explicit run request. This is an anti-stale receipt, NOT GPU attestation.
static char s_stage231Nonce[33] = {};

static bool loadStage231Nonce()
{
    FILE* request=std::fopen("sdmc:/switch/heman-stage230/run_nonce.txt","rb");
    if(!request) return false;
    char input[34] = {};
    const size_t got=std::fread(input,1u,sizeof input,request);
    const bool closed=std::fclose(request)==0;
    if(!closed || got!=33u || input[32]!='\n')
        return false;
    for(size_t i=0;i<32u;++i) {
        const char c=input[i];
        if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))
            return false;
    }
    std::memcpy(s_stage231Nonce,input,32u);
    s_stage231Nonce[32]='\0';
    return true;
}

// Invalidate any previous capture BEFORE starting GPU work, including failed
// shader initialization or GPU hangs. Never let an old receipt look fresh.
static bool prepareStage230Capture()
{
    if(::mkdir("sdmc:/switch",0777)!=0 && errno!=EEXIST) return false;
    if(::mkdir("sdmc:/switch/heman-stage230",0777)!=0 && errno!=EEXIST)
        return false;
    for(const char* path : {
        "sdmc:/switch/heman-stage230/readback.receipt",
        "sdmc:/switch/heman-stage230/readback.rgba",
        "sdmc:/switch/heman-stage230/readback.rgba.tmp",
        "sdmc:/switch/heman-stage230/readback.receipt.tmp",
        "sdmc:/switch/heman-stage230/upload.rgba",
        "sdmc:/switch/heman-stage230/upload.rgba.tmp",
        "sdmc:/switch/heman-stage230/gpu_phase.txt",
        "sdmc:/switch/heman-stage230/gpu_phase.tmp",
        "sdmc:/switch/heman-stage230/guest_exit.txt",
        "sdmc:/switch/heman-stage230/guest_exit.tmp"
    }) {
        if(std::remove(path)!=0 && errno!=ENOENT) return false;
    }
    return true;
}

// Stage230: preserve *observed* bytes without relying on stdout routing.
// The receipt is committed last; a missing receipt means an incomplete capture.
// This is a synthetic fixture. Neither the SD card nor this file proves GPU
// hardware provenance; a real runner/device observation is still required.
static bool saveStage230Capture(const uint8_t* pixels, uint32_t mismatches)
{
    static constexpr const char* base="sdmc:/switch/heman-stage230";
    static constexpr const char* imageTmp="sdmc:/switch/heman-stage230/readback.rgba.tmp";
    static constexpr const char* imageFinal="sdmc:/switch/heman-stage230/readback.rgba";
    static constexpr const char* receiptTmp="sdmc:/switch/heman-stage230/readback.receipt.tmp";
    static constexpr const char* receiptFinal="sdmc:/switch/heman-stage230/readback.receipt";
    if(!pixels) return false;
    if(::mkdir("sdmc:/switch",0777)!=0 && errno!=EEXIST) return false;
    if(::mkdir(base,0777)!=0 && errno!=EEXIST) return false;
    // Fail closed against a successful receipt from a prior invocation.
    if(std::remove(receiptFinal)!=0 && errno!=ENOENT) return false;
    std::remove(imageTmp);
    std::remove(receiptTmp);
    FILE* output=std::fopen(imageTmp,"wb");
    if(!output) return false;
    const bool wrote=std::fwrite(pixels,1u,kGpuUploadBytes,output)==kGpuUploadBytes;
    const bool synced=std::fflush(output)==0;
    const bool closed=std::fclose(output)==0;
    if(!wrote||!synced||!closed) {
        std::remove(imageTmp);
        return false;
    }
    if(std::rename(imageTmp,imageFinal)!=0) {
        std::remove(imageTmp);
        return false;
    }
    FILE* receipt=std::fopen(receiptTmp,"wb");
    if(!receipt) return false;
    const int n=std::fprintf(receipt,
        "STAGE230_GPU_READBACK width=%u height=%u bytes=%u pixels=%u mismatches=%u nonce=%s\n",
        kWidth,kHeight,kGpuUploadBytes,kWidth*kHeight,mismatches,s_stage231Nonce);
    const bool receiptSynced=std::fflush(receipt)==0;
    const bool receiptClosed=std::fclose(receipt)==0;
    if(n<=0||!receiptSynced||!receiptClosed) {
        std::remove(receiptTmp);
        return false;
    }
    if(std::rename(receiptTmp,receiptFinal)!=0) {
        std::remove(receiptTmp);
        return false;
    }
    return true;
}

// Stage234: durable stage-local progress marker for diagnosing a real GPU
// execution attempt when stdout is not exposed by the Switch launcher.
// Each record is a last-known CPU checkpoint, NOT independent proof of GPU
// hardware activity. Only an exact nonce-bound full capture can be evaluated.
static bool saveStage234Checkpoint(const char* phase)
{
    if(!phase || !s_stage231Nonce[0]) return false;
    constexpr const char* temporary="sdmc:/switch/heman-stage230/gpu_phase.tmp";
    constexpr const char* committed="sdmc:/switch/heman-stage230/gpu_phase.txt";
    FILE* out=std::fopen(temporary,"wb");
    if(!out) return false;
    const int count=std::fprintf(out,"STAGE234_GPU_PHASE nonce=%s phase=%s\n",
                                s_stage231Nonce,phase);
    const bool flushed=std::fflush(out)==0;
    const bool closed=std::fclose(out)==0;
    if(count<=0 || !flushed || !closed ||
       std::rename(temporary,committed)!=0) {
        std::remove(temporary);
        return false;
    }
    return true;
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
    // Stage234: a transfer-produced texture must be made visible to the
    // fragment sampler. Queue idle is not a texture cache invalidation.
    cmd.barrier(DkBarrier_Full,
                DkInvalidateFlags_Image|DkInvalidateFlags_Descriptors|
                DkInvalidateFlags_Shader);
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
    cmd.bindVtxAttribState({attribs[0],attribs[1]});
    cmd.bindVtxBufferState({buffers[0]});
    cmd.bindVtxBuffer(0,vertexMem.getGpuAddr(),sizeof kQuad);
    cmd.bindTextures(DkStage_Fragment,0,dkMakeTextureHandle(0,0));
    cmd.draw(DkPrimitive_TriangleStrip,4,1,0,0);
    cmd.barrier(DkBarrier_Full,DkInvalidateFlags_Image);
    cmd.copyImageToBuffer(outputView,{0u,0u,0u,kWidth,kHeight,1u},
                          {readbackMem.getGpuAddr(),kWidth*4u,kGpuUploadBytes});
    queue.submitCommands(cmd.finishList());
    queue.waitIdle();
    if(!saveStage234Checkpoint("05_render_queue_idle")) return 29;
    const auto* pixels=static_cast<const uint8_t*>(readbackMem.getCpuAddr());
    // Stage229 prints the *complete GPU output* before checking it. An
    // independent host verifier must compare these 512 bytes to the
    // synthetic C99/reference fixture. This is never emitted by build CI.
    std::printf("STAGE229_GPU_READBACK_BEGIN width=%u height=%u bytes=%u\n",
                kWidth,kHeight,kGpuUploadBytes);
    for(uint32_t y=0;y<kHeight;++y) {
        std::printf("STAGE229_GPU_READBACK_ROW y=%u rgba=",y);
        for(uint32_t x=0;x<kWidth*4u;++x)
            std::printf("%02x",(unsigned)pixels[y*kWidth*4u+x]);
        std::printf("\n");
    }
    std::fflush(stdout);
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
    std::printf("STAGE229_GPU_READBACK_END mismatches=%u\n",mismatches);
    std::printf("STAGE228_GPU_QUAD_READBACK pixels=%u mismatches=%u\n",
                kWidth*kHeight,mismatches);
    // Stage230 requires a persistent capture even if stdout is unavailable.
    // Save mismatching bytes too, so a failed run remains diagnosable.
    const bool captured=saveStage230Capture(pixels,mismatches);
    if(!captured)
        std::fprintf(stderr,"STAGE230_CAPTURE_FAILED: cannot persist SD readback\n");
    if(captured && !saveStage234Checkpoint("06_receipt_committed")) return 29;
    (void)texture; // texture lifetime is owned by the caller through queue.waitIdle().
    return captured?(mismatches==0?0:25):26;
}

// Stage233 stores a separately copied GPU texture. The file is written by
// GPU->CPU readback, never by the original staging pointer. The Stage230
// completed render receipt remains absent if upload verification fails.
static bool saveStage233Upload(const uint8_t* pixels)
{
    if(!pixels) return false;
    constexpr const char* temporary="sdmc:/switch/heman-stage230/upload.rgba.tmp";
    constexpr const char* committed="sdmc:/switch/heman-stage230/upload.rgba";
    FILE* out=std::fopen(temporary,"wb");
    if(!out) return false;
    const bool wrote=std::fwrite(pixels,1u,kGpuUploadBytes,out)==kGpuUploadBytes;
    const bool flushed=std::fflush(out)==0;
    const bool closed=std::fclose(out)==0;
    if(!wrote||!flushed||!closed || std::rename(temporary,committed)!=0) {
        std::remove(temporary);
        return false;
    }
    return true;
}

// Stage241: CPU-written exit status from the actual NRO control path.
// A host emulator process can exit 0 without executing this guest code.
// This nonce-linked receipt is diagnostic evidence, not GPU attestation.
static bool saveStage241GuestExit(int guestCode)
{
    if(!s_stage231Nonce[0]) return false;
    constexpr const char* temp="sdmc:/switch/heman-stage230/guest_exit.tmp";
    constexpr const char* target="sdmc:/switch/heman-stage230/guest_exit.txt";
    FILE* f=std::fopen(temp,"wb");
    if(!f) return false;
    const int count=std::fprintf(f,"STAGE241_GUEST_EXIT nonce=%s code=%d\n",
                                 s_stage231Nonce,guestCode);
    const bool flushed=std::fflush(f)==0;
    const bool closed=std::fclose(f)==0;
    if(count<=0 || !flushed || !closed || std::rename(temp,target)!=0) {
        std::remove(temp);
        return false;
    }
    return true;
}

static int runStage241Guest(int argc, char** argv)
{
    (void)argc; (void)argv;
    if(!buildSyntheticSource()) return 2;
    if(!prepareStage230Capture()) return 27; // no SD evidence path
    if(!loadStage231Nonce()) return 28; // refuse unbound / stale sessions
    if(!saveStage234Checkpoint("01_nonce_validated")) return 29;
    const Result romfsResult=romfsInit();
    if(R_FAILED(romfsResult)) return 11;
    const bool shadersReady=
        verifyPackagedShader("romfs:/shaders/padded_texture_vsh.dksh",DkStage_Vertex) &&
        verifyPackagedShader("romfs:/shaders/padded_texture_fsh.dksh",DkStage_Fragment);
    if(!shadersReady) { romfsExit(); return 12; }
    // Unlike Stage225's libnx software framebuffer this creates an actual
    // Tegra image, stages CPU-generated pixels and submits a GPU copy command.
    auto device = dk::DeviceMaker{}.create();
    if(!device) return 3;
    auto queue = dk::QueueMaker{device}.setFlags(DkQueueFlags_Graphics).create();
    if(!queue) return 4;

    // Load the exact packaged DKSH programs into GPU code memory.
    // Inline DKSH control+code is SDK-supported; Stage232 checks strict bounds.
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
    if(!saveStage234Checkpoint("02_shaders_loaded")) return 29;

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
    // rowLength is a byte pitch, not a pixel count (see deko3d dk_image.cpp).
    // Specify 64 bytes/row and 512 bytes/layer explicitly instead of relying
    // on the implicit zero-value pitch convention.
    constexpr uint32_t rowBytes=kWidth*4u;
    cmds.copyBufferToImage({staging.getGpuAddr(),rowBytes,kGpuUploadBytes},
                           view,{0,0,0,kWidth,kHeight,1});
    queue.submitCommands(cmds.finishList());
    queue.waitIdle();
    if(!saveStage234Checkpoint("03_texture_upload_queue_idle")) return 29;

    // Stage233 is a SECOND GPU transfer: image -> a distinct uncached CPU
    // buffer. It is not the original staging buffer and not the rendered
    // target. A successful 128-pixel upload test narrows later shader bugs.
    auto uploadReadback=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    auto uploadCmdMem=dk::MemBlockMaker{device,DK_MEMBLOCK_ALIGNMENT}
        .setFlags(DkMemBlockFlags_CpuUncached|DkMemBlockFlags_GpuCached).create();
    if(!uploadReadback||!uploadCmdMem||!uploadReadback.getCpuAddr()) return 15;
    std::memset(uploadReadback.getCpuAddr(),0xa5,kGpuUploadBytes);
    auto uploadCmd=dk::CmdBufMaker{device}.create();
    if(!uploadCmd) return 15;
    uploadCmd.addMemory(uploadCmdMem,0u,DK_MEMBLOCK_ALIGNMENT);
    uploadCmd.copyImageToBuffer(
        view,{0u,0u,0u,kWidth,kHeight,1u},
        {uploadReadback.getGpuAddr(),rowBytes,kGpuUploadBytes});
    queue.submitCommands(uploadCmd.finishList());
    queue.waitIdle();

    const auto* uploaded=static_cast<const uint8_t*>(uploadReadback.getCpuAddr());
    const bool uploadSaved=saveStage233Upload(uploaded);
    if(!uploadSaved) return 17;
    uint32_t uploadMismatches=0;
    for(uint32_t p=0;p<kGpuUploadBytes;p+=4u) {
        if(std::memcmp(uploaded+p,s_padded+p,4u)!=0) {
            if(uploadMismatches<8u)
                std::printf("STAGE233_UPLOAD_PIXEL_MISMATCH pixel=%u\n",p/4u);
            ++uploadMismatches;
        }
    }
    std::printf("STAGE233_GPU_UPLOAD_ROUNDTRIP pixels=%u mismatches=%u\n",
                kWidth*kHeight,uploadMismatches);
    std::fflush(stdout);
    if(uploadMismatches) return 16;
    if(!saveStage234Checkpoint("04_upload_pixels_match")) return 29;

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

int main(int argc, char** argv)
{
    const int guestCode=runStage241Guest(argc,argv);
    // Missing/invalid nonce is already a hard failure; do not invent a
    // status without a valid session. Other failures are recorded too.
    if(s_stage231Nonce[0] && !saveStage241GuestExit(guestCode))
        return 30;
    return guestCode;
}
