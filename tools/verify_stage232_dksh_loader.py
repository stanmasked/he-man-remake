#!/usr/bin/env python3
"""Stage232 strict one-program DKSH preflight, independent of GPU execution."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct

HEADER = struct.Struct("<6I")
PROGRAM = struct.Struct("<6I")
MAGIC = 0x48534B44
SHADER_ALIGNMENT = 0x100
CODE_UNUSABLE = 0x400
CODE_MEM_BYTES = 0x4000
MAX_SECTION = 0x1000
PROGRAM_BYTES = 64


class ShaderLayoutError(ValueError):
    pass


def inspect(blob: bytes, stage: str) -> dict:
    if stage not in ("vertex", "fragment"):
        raise ShaderLayoutError("stage must be vertex or fragment")
    if not isinstance(blob, bytes) or len(blob) < HEADER.size:
        raise ShaderLayoutError("missing complete DKSH header")
    magic, hdr, ctrl, code, program_off, count = HEADER.unpack_from(blob)
    if magic != MAGIC:
        raise ShaderLayoutError("invalid DKSH magic")
    if hdr != HEADER.size or count != 1:
        raise ShaderLayoutError("wrong header size or program count")
    if not hdr+PROGRAM_BYTES <= ctrl <= MAX_SECTION or ctrl % SHADER_ALIGNMENT:
        raise ShaderLayoutError("invalid control section size/alignment")
    if not SHADER_ALIGNMENT <= code <= MAX_SECTION or code % SHADER_ALIGNMENT:
        raise ShaderLayoutError("invalid machine-code section size/alignment")
    if not hdr <= program_off or program_off+PROGRAM_BYTES > ctrl:
        raise ShaderLayoutError("program header extends beyond control section")
    if len(blob) != ctrl+code:
        raise ShaderLayoutError("truncated or trailing shader data")
    shader_type, entrypoint, registers, constbuf_off, constbuf_size, scratch_size = (
        PROGRAM.unpack_from(blob, program_off))
    if shader_type != {"vertex": 0, "fragment": 1}[stage]:
        raise ShaderLayoutError("unexpected DKSH shader stage")
    if entrypoint >= code:
        raise ShaderLayoutError("shader entrypoint beyond code section")
    if constbuf_size and constbuf_off+constbuf_size > code:
        raise ShaderLayoutError("constbuf beyond shader code section")
    return {
        "stage": stage,
        "dksh_bytes": len(blob),
        "control_bytes": ctrl,
        "code_bytes": code,
        "program_offset": program_off,
        "program_count": count,
        "entrypoint": entrypoint,
        "num_registers": registers,
        "gpu_executed": False,
    }


def verify_pair(vertex: bytes, fragment: bytes,
                memblock_size: int = CODE_MEM_BYTES,
                offsets: tuple[int, int] = (0, 4096)) -> dict:
    v = inspect(vertex, "vertex")
    f = inspect(fragment, "fragment")
    if vertex == fragment:
        raise ShaderLayoutError("identical shaders")
    if memblock_size <= CODE_UNUSABLE or len(offsets) != 2:
        raise ShaderLayoutError("insufficient GPU code block")
    used = []
    for blob, off in zip((vertex, fragment), offsets):
        if type(off) is not int or off < 0 or off % SHADER_ALIGNMENT:
            raise ShaderLayoutError("unaligned GPU shader slot")
        if off+len(blob) > memblock_size-CODE_UNUSABLE:
            raise ShaderLayoutError("shader code enters unusable tail")
        used.append((off, off+len(blob)))
    if used[0][0] < used[1][1] and used[1][0] < used[0][1]:
        raise ShaderLayoutError("GPU shader code slots overlap")
    return {
        "schema": "stage232-verified-dksh-layout-v1",
        "vertex": v,
        "fragment": f,
        "code_memblock_size": memblock_size,
        "unusable_tail_bytes": CODE_UNUSABLE,
        "code_slots": [list(slot) for slot in used],
        "hardware_gpu_execution_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vertex", type=Path)
    parser.add_argument("fragment", type=Path)
    parser.add_argument("--nro", required=True, type=Path)
    args = parser.parse_args()
    from verify_stage227_dksh_bundle import inspect_embedded_nro_shaders
    vb = args.vertex.read_bytes()
    fb = args.fragment.read_bytes()
    data = verify_pair(vb, fb)
    data["nro_romfs"] = inspect_embedded_nro_shaders(args.nro.read_bytes(), vb, fb)
    print(json.dumps(data, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
