"""Stage214: owner-local PNG-backed CPU preview of a multi-Symbol frame.

The preview uses original TextureData alpha/filter/wrap selectors and the
existing bounded Python sampler. PNG pixels and per-resource details remain
in process memory; only an aggregate report and an explicitly requested PNG
under ignored local_reports/ are written. This is not GPU or runtime parity.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .collision_inventory import private_output_path
from .physics_shape_census import SCREENS
from .private_multisymbol_frame_audit import (
    _parse_active_mask,
    _parse_region,
    audit_private_multisymbol_frame,
)
from .private_single_symbol_frame_decoder import _private_png_output_path
from .symbol_frame_assembler import assemble_symbol_frame
from .symbol_frame_render_plan import (
    PlayerTransform,
    SymbolLayerInput,
    build_symbol_frame_render_plan,
)
from .symbol_render_contract import SymbolRenderContract
from .textured_quad_reference import (
    FrameBlendState,
    RasterProjection,
    TexturePixels,
    TexturedQuadRenderError,
    SoftwareFrameResult,
    render_textured_frame,
)


class PrivateCPUFramePreviewError(ValueError):
    """A private CPU frame preview could not be rendered without guessing."""


def render_private_cpu_frame_preview(
    ipa: Path,
    regions: tuple[tuple[int, int], tuple[int, int]],
    alias: str,
    variant: int,
    direction: str,
    frame_index: int,
    *,
    screen: str = SCREENS[0],
    active_mask: int = 0,
) -> tuple[dict, SoftwareFrameResult]:
    """Decode, assemble, and rasterize one private source frame in CPU memory."""
    if screen not in SCREENS:
        raise PrivateCPUFramePreviewError("Unsupported source resolution pack")

    details: list = []
    source_report = audit_private_multisymbol_frame(
        ipa,
        regions,
        alias,
        variant,
        direction,
        frame_index,
        active_mask=active_mask,
        source_screen_group=screen,
        _private_details=details,
        _include_texture_pixels=True,
    )
    if len(details) != 1:
        raise PrivateCPUFramePreviewError("Private frame resolver did not return one detail set")
    private = details[0]
    symbols = private["symbols"]
    rectangles = private["rectangles"]
    dimensions = private["png_dimensions"]
    wraps = private["wrap_codes"]
    filters = private["filter_modes"]
    texture_rgba = private["texture_rgba"]
    texture_keys = private["texture_keys"]
    alpha_flags = private["alpha_transform_flags"]
    payload_selectors = private["payload_selectors"]
    count = len(symbols)
    if not (count == len(rectangles) == len(dimensions) == len(wraps)
            == len(filters) == len(texture_rgba) == len(texture_keys)
            == len(alpha_flags) == len(payload_selectors)):
        raise PrivateCPUFramePreviewError("Decoded per-Symbol texture metadata lengths differ")
    if any(selector != 0 for selector in payload_selectors):
        raise PrivateCPUFramePreviewError("Only the confirmed PNG payload path is supported")

    layers = []
    textures_by_slot = {}
    try:
        for order, symbol in enumerate(symbols):
            contract = SymbolRenderContract.from_serialized_fields(
                symbol["serialized_fields"],
                symbol["transform_values"],
                symbol["serialized_tail"],
            )
            layers.append(SymbolLayerInput(
                source_order=order,
                contract=contract,
                cut_rectangle=rectangles[order],
                png_dimensions=dimensions[order],
                wrap_codes=wraps[order],
                texture_slot=order,
            ))
            width, height = dimensions[order]
            textures_by_slot[order] = TexturePixels(
                width,
                height,
                texture_rgba[order],
                wraps[order][0],
                wraps[order][1],
                filter_mode_code=filters[order],
            )
        plan = build_symbol_frame_render_plan(
            tuple(layers),
            active_mask=active_mask,
            user_rgba=(1.0, 1.0, 1.0, 1.0),
        )
        extents = tuple((rectangle[2], rectangle[3]) for rectangle in rectangles)
        assembly = assemble_symbol_frame(
            plan,
            extents,
            active_mask=active_mask,
            player_transform=PlayerTransform(),
        )
        packets = assembly.packets
        if not packets:
            raise PrivateCPUFramePreviewError("Selected frame has no drawable Symbols under this mask")

        x_values = [packet.xy[index] for packet in packets for index in range(0, 8, 2)]
        y_values = [packet.xy[index] for packet in packets for index in range(1, 8, 2)]
        min_x, max_x = min(x_values), max(x_values)
        min_y, max_y = min(y_values), max(y_values)
        extent_x, extent_y = max_x - min_x, max_y - min_y
        if not all(math.isfinite(value) for value in (extent_x, extent_y)) or extent_x <= 0 or extent_y <= 0:
            raise PrivateCPUFramePreviewError("Selected frame has invalid or empty geometry bounds")

        # The paired source packs were verified to scale geometry exactly 2x.
        # Use corresponding transparent margins without scaling the geometry.
        margin = 8 if screen == SCREENS[0] else 16
        width = math.ceil(extent_x) + 2 * margin
        height = math.ceil(extent_y) + 2 * margin
        projection = RasterProjection(tx=margin - min_x, ty=margin - min_y)
        rendered = render_textured_frame(
            packets,
            textures_by_slot,
            width=width,
            height=height,
            projection=projection,
            frame_blend=FrameBlendState(),
            clear_rgba=(0, 0, 0, 0),
        )
    except PrivateCPUFramePreviewError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, TexturedQuadRenderError):
            raise PrivateCPUFramePreviewError(
                "Frame uses an unsupported texture sampler, blend state, or geometry"
            ) from exc
        raise PrivateCPUFramePreviewError("Private frame could not be rendered without guessing") from exc

    unique_index_by_key = {}
    for index, key in enumerate(texture_keys):
        unique_index_by_key.setdefault(key, index)
    unique_indices = tuple(unique_index_by_key.values())
    unique_filters = [filters[index] for index in unique_indices]
    unique_alpha_flags = [alpha_flags[index] for index in unique_indices]
    report = {
        "classification": "private_png_backed_cpu_frame_preview",
        "source_resolution_pack": screen,
        "direction": direction,
        "frame_index": frame_index,
        "source_symbol_count": source_report["source_symbol_count"],
        "resolved_symbol_count": source_report["resolved_symbol_count"],
        "cpu_frame_packet_count": rendered.packets_considered,
        "cpu_frame_packets_with_coverage": rendered.packets_with_coverage,
        "cpu_frame_pixel_samples": rendered.pixel_samples,
        "texture_binding_count": count,
        "unique_texture_count": len(unique_indices),
        "native_texture_filter_mode_counts_by_unique_texture": {
            "nearest": unique_filters.count(0),
            "linear": unique_filters.count(1),
            "unsupported_mipmap": unique_filters.count(2),
        },
        "unique_textures_with_alpha_transform_enabled": unique_alpha_flags.count(1),
        "all_payloads_use_png_path": all(payload_selectors[index] == 0 for index in unique_indices),
        "all_source_rectangles_in_bounds": source_report["all_sprite_rectangles_in_bounds"],
        "all_source_pngs_validated": source_report["all_source_pngs_validated"],
        "active_mask_source": "CLI-supplied; runtime active mask not recovered",
        "player_transform": "identity assumption",
        "projection": "translate native XY bounds to a transparent content canvas; no scale or camera inferred",
        "output_width": rendered.width,
        "output_height": rendered.height,
        "gpu_submission_verified": False,
        "original_runtime_pixel_parity_verified": False,
        "full_scene_placement_verified": False,
        "private_resource_details_exported": False,
    }
    return report, rendered


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--region", action="append", required=True, type=_parse_region,
                        help="private GO byte window START:END; provide exactly two")
    parser.add_argument("--alias", required=True, help="private local alias selector")
    parser.add_argument("--variant", required=True, type=int, choices=(0, 1))
    parser.add_argument("--direction", required=True, choices=("east", "west"))
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--active-mask", type=_parse_active_mask, default=0)
    parser.add_argument("--screen", choices=SCREENS, default=SCREENS[0])
    parser.add_argument("--preview-out", required=True, type=Path,
                        help="PNG destination under ignored local_reports/")
    parser.add_argument("--report-out", required=True, type=Path,
                        help="aggregate JSON destination under ignored local_reports/")
    args = parser.parse_args(argv)
    if len(args.region) != 2:
        parser.error("exactly two --region values are required")

    preview_path = _private_png_output_path(args.preview_out)
    report_path = private_output_path(args.report_out)
    report, rendered = render_private_cpu_frame_preview(
        args.ipa,
        tuple(args.region),
        args.alias,
        args.variant,
        args.direction,
        args.frame,
        screen=args.screen,
        active_mask=args.active_mask,
    )
    from PIL import Image
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    Image.frombytes("RGBA", (rendered.width, rendered.height), rendered.rgba).save(
        preview_path, format="PNG"
    )
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(
        "Private CPU preview rendered; "
        f"symbols={report['source_symbol_count']}, "
        f"packets={report['cpu_frame_packet_count']}, "
        f"size={report['output_width']}x{report['output_height']}; "
        "GPU/runtime parity remains unverified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
