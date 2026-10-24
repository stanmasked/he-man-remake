#version 460

// Stage227: invented fullscreen-quad input positions and UVs.
// No original artwork, positions, player or camera data.
layout(location = 0) in vec2 inPosition;
layout(location = 1) in vec2 inTexCoord;
layout(location = 0) out vec2 sampleUV;

void main()
{
    gl_Position = vec4(inPosition, 0.0, 1.0);
    sampleUV = inTexCoord;
}
