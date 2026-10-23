"""Stage201: bounded, asset-free multi-Symbol frame packet assembly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .symbol_frame_render_plan import (
    PlayerTransform, SymbolDrawCommand, SymbolFrameRenderPlan,
)
from .symbol_mesh_geometry import (
    SymbolMeshGeometryError, build_symbol_quad_geometry,
    expand_native_uv_corners, _validate_command,
)


MAX_SYMBOL_FRAME_COMMANDS = 1024
_S32_MIN = -(1 << 31)
_S32_MAX = (1 << 31) - 1


class SymbolFrameAssemblyError(ValueError):
    """Invalid, oversized, or internally inconsistent frame assembly."""


@dataclass(frozen=True)
class NativeFramePacket:
    """One CPU-side native draw packet; not a GPU command or rendered image."""

    source_order: int
    cut_handle: int
    front_face_flip: bool
    xy: tuple[float, ...]
    uv: tuple[float, ...]
    rgba: tuple[float, float, float, float]
    blend_override: tuple[int, int] | None
    texture_slot: int | None = None


@dataclass(frozen=True)
class NativeFrameAssembly:
    """Bounded source-order packet sequence ready for a future backend adapter."""

    packets: tuple[NativeFramePacket, ...]

    @property
    def packet_count(self) -> int:
        return len(self.packets)

    @property
    def source_order(self) -> tuple[int, ...]:
        return tuple(packet.source_order for packet in self.packets)


def assemble_symbol_frame(
    plan: SymbolFrameRenderPlan,
    cut_extents: Sequence[tuple[int, int]],
    *,
    active_mask: int,
    player_transform: PlayerTransform | None = None,
) -> NativeFrameAssembly:
    """Resolve known cut extents into transactional CPU-side draw packets.

    cut_extents parallels all source commands, including masked commands.
    Every source command is validated before packet creation. Masked commands
    are omitted, but surviving packets retain their original source_order.
    No resource lookup, texture decoding, GPU submission, or pixel rendering
    is performed here.
    """
    if not isinstance(plan, SymbolFrameRenderPlan):
        raise SymbolFrameAssemblyError("plan must be a SymbolFrameRenderPlan")
    if type(active_mask) is not int or not _S32_MIN <= active_mask <= _S32_MAX:
        raise SymbolFrameAssemblyError("active_mask must be a signed 32-bit integer")
    count = len(plan.commands)
    if count > MAX_SYMBOL_FRAME_COMMANDS:
        raise SymbolFrameAssemblyError("frame exceeds the bounded command limit")
    if not isinstance(cut_extents, (tuple, list)) or len(cut_extents) != count:
        raise SymbolFrameAssemblyError("cut_extents must parallel every source command")
    if player_transform is None:
        player_transform = PlayerTransform()
    if not isinstance(player_transform, PlayerTransform):
        raise SymbolFrameAssemblyError("player_transform must be a PlayerTransform")

    normalized_extents: list[tuple[int, int]] = []
    for index, extent in enumerate(cut_extents):
        if (not isinstance(extent, (tuple, list)) or len(extent) != 2
                or any(type(value) is not int or not _S32_MIN <= value <= _S32_MAX
                       for value in extent)):
            raise SymbolFrameAssemblyError(
                f"cut_extents[{index}] must contain signed 32-bit width and height"
            )
        normalized_extents.append((extent[0], extent[1]))

    # Validate the complete command stream before assembling the first packet.
    for expected_order, command in enumerate(plan.commands):
        if not isinstance(command, SymbolDrawCommand):
            raise SymbolFrameAssemblyError("every plan entry must be a SymbolDrawCommand")
        if command.source_order != expected_order:
            raise SymbolFrameAssemblyError("source order must be contiguous and unchanged")
        try:
            _validate_command(command)
        except (ValueError, TypeError, OverflowError) as exc:
            raise SymbolFrameAssemblyError("draw command failed validation") from exc
        if (command.texture_slot is not None
                and (type(command.texture_slot) is not int
                     or not 0 <= command.texture_slot <= _S32_MAX)):
            raise SymbolFrameAssemblyError("texture_slot must be a non-negative signed 32-bit integer or None")
        expected_draw_enabled = (command.symbol_mask & active_mask) == 0
        if command.draw_enabled != expected_draw_enabled:
            raise SymbolFrameAssemblyError(
                "plan mask state does not match the assembler active_mask"
            )

    packets: list[NativeFramePacket] = []
    try:
        for command, (width, height) in zip(plan.commands, normalized_extents):
            if (command.symbol_mask & active_mask) != 0:
                continue
            geometry = build_symbol_quad_geometry(
                command, width, height, player_transform
            )
            uv_pairs = expand_native_uv_corners(command)
            packets.append(NativeFramePacket(
                source_order=command.source_order,
                cut_handle=command.cut_handle,
                texture_slot=command.texture_slot,
                front_face_flip=geometry.front_face_flip,
                xy=geometry.flat_xy,
                uv=tuple(value for pair in uv_pairs for value in pair),
                rgba=tuple(command.vertex_rgba),
                blend_override=command.blend_override,
            ))
    except (SymbolMeshGeometryError, ValueError, TypeError, OverflowError) as exc:
        raise SymbolFrameAssemblyError(
            "frame assembly failed; no partial frame is returned"
        ) from exc

    if len(packets) > MAX_SYMBOL_FRAME_COMMANDS:
        raise SymbolFrameAssemblyError("assembled frame exceeds the bounded command limit")
    return NativeFrameAssembly(tuple(packets))
