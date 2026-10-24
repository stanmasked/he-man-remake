#version 460

// Stage227 GPU sampler source; the actual draw/render target is Stage228.
// Stage226 stages RGBA8 data; do not reinterpret black padded RGB alpha.
layout(location = 0) in vec2 sampleUV;
layout(location = 0) out vec4 outColor;
layout(binding = 0) uniform sampler2D paddedTexture;

void main()
{
    outColor = texture(paddedTexture, sampleUV);
}
