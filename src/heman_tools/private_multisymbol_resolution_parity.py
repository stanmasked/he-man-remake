"""Stage205: private paired-resolution multi-Symbol frame parity audit.

Original source records and per-Symbol geometry remain in memory only. The
public report contains aggregate booleans and counts, never names, coordinates,
byte offsets, source bytes, or image data. This is CPU reference parity, not
GPU submission or original-runtime pixel verification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .collision_inventory import private_output_path
from .physics_shape_census import SCREENS
from .private_multisymbol_frame_audit import (
    _parse_active_mask,
    _parse_region,
    audit_private_multisymbol_frame,
)
from .symbol_frame_assembler import assemble_symbol_frame
from .symbol_frame_render_plan import (
    PlayerTransform,
    SymbolLayerInput,
    build_symbol_frame_render_plan,
)
from .symbol_render_contract import SymbolRenderContract


class ResolutionParityError(ValueError):
    """Invalid paired source frame or inconsistent resolution-pack evidence."""


def _pack_summary(report: dict) -> dict:
    fields = (
        "source_symbol_count",
        "resolved_symbol_count",
        "all_sprite_rectangles_in_bounds",
        "all_resource_links_resolved_uniquely",
        "all_source_pngs_validated",
        "cpu_frame_packet_count",
        "cpu_frame_packet_vertex_count",
        "cpu_frame_packet_uv_pair_count",
        "cpu_frame_packet_color_channel_count",
        "cpu_frame_packet_finite",
        "cpu_frame_packet_source_order_preserved",
        "masked_symbol_count",
    )
    return {key: report[key] for key in fields}


def _packets(details: dict, active_mask: int):
    symbols = details["symbols"]
    rectangles = details["rectangles"]
    dimensions = details["png_dimensions"]
    wraps = details["wrap_codes"]
    if not (len(symbols) == len(rectangles) == len(dimensions) == len(wraps)):
        raise ResolutionParityError("Private per-Symbol metadata lengths differ")
    layers = []
    for order, symbol in enumerate(symbols):
        try:
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
            ))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ResolutionParityError("Private Symbol geometry could not be reconstructed") from exc
    plan = build_symbol_frame_render_plan(
        tuple(layers), active_mask=active_mask, user_rgba=(1.0, 1.0, 1.0, 1.0)
    )
    extents = tuple((rectangle[2], rectangle[3]) for rectangle in rectangles)
    assembly = assemble_symbol_frame(
        plan, extents, active_mask=active_mask, player_transform=PlayerTransform()
    )
    return assembly.packets


def _double_tuple(left, right) -> bool:
    return len(left) == len(right) and all(b == 2 * a for a, b in zip(left, right))


def _same_symbol_fields(med: dict, xlarge: dict) -> tuple[bool, bool]:
    left = med["symbols"]
    right = xlarge["symbols"]
    if len(left) != len(right):
        return False, False
    identity_and_visual = True
    offsets_double = True
    for a, b in zip(left, right):
        if a.get("name") != b.get("name"):
            identity_and_visual = False
            offsets_double = False
            continue
        af = tuple(a.get("serialized_fields", ()))
        bf = tuple(b.get("serialized_fields", ()))
        at = tuple(a.get("transform_values", ()))
        bt = tuple(b.get("transform_values", ()))
        ai = tuple(a.get("serialized_tail", ()))
        bi = tuple(b.get("serialized_tail", ()))
        if len(af) != 4 or len(bf) != 4:
            identity_and_visual = False
            offsets_double = False
            continue
        if af[:2] != bf[:2] or at != bt or ai != bi:
            identity_and_visual = False
        if not _double_tuple(af[2:], bf[2:]):
            offsets_double = False
    return identity_and_visual, offsets_double


def summarize_resolution_parity(
    med_report: dict,
    xlarge_report: dict,
    med_details: dict,
    xlarge_details: dict,
    *,
    active_mask: int,
) -> dict:
    """Compare paired packs in memory and return only safe aggregate evidence."""
    med_symbols = med_details["symbols"]
    xl_symbols = xlarge_details["symbols"]
    med_rects = med_details["rectangles"]
    xl_rects = xlarge_details["rectangles"]
    med_dims = med_details["png_dimensions"]
    xl_dims = xlarge_details["png_dimensions"]
    med_wraps = med_details["wrap_codes"]
    xl_wraps = xlarge_details["wrap_codes"]

    same_count = len(med_symbols) == len(xl_symbols)
    identity_visual_match, offsets_double = _same_symbol_fields(med_details, xlarge_details)
    rectangles_double = (
        len(med_rects) == len(xl_rects)
        and all(_double_tuple(a, b) for a, b in zip(med_rects, xl_rects))
    )
    dimensions_double = (
        len(med_dims) == len(xl_dims)
        and all(_double_tuple(a, b) for a, b in zip(med_dims, xl_dims))
    )
    wraps_match = med_wraps == xl_wraps and len(med_wraps) == len(xl_wraps)
    resource_chain_match = (
        med_details.get("resolved_links") == xlarge_details.get("resolved_links")
        and len(med_details.get("resolved_links", ())) == len(med_symbols)
    )

    med_packets = _packets(med_details, active_mask)
    xl_packets = _packets(xlarge_details, active_mask)
    packet_count_match = len(med_packets) == len(xl_packets)
    source_order_match = (
        tuple(packet.source_order for packet in med_packets)
        == tuple(packet.source_order for packet in xl_packets)
    )
    uv_match = packet_count_match and all(
        a.uv == b.uv for a, b in zip(med_packets, xl_packets)
    )
    geometry_double = packet_count_match and all(
        _double_tuple(a.xy, b.xy) for a, b in zip(med_packets, xl_packets)
    )
    color_blend_winding_match = packet_count_match and all(
        a.rgba == b.rgba
        and a.blend_override == b.blend_override
        and a.front_face_flip == b.front_face_flip
        for a, b in zip(med_packets, xl_packets)
    )

    link_bounds_ok = all(
        report["all_resource_links_resolved_uniquely"]
        and report["all_source_pngs_validated"]
        and report["all_sprite_rectangles_in_bounds"]
        and report["cpu_frame_packet_finite"]
        and report["cpu_frame_packet_source_order_preserved"]
        for report in (med_report, xlarge_report)
    )
    checks = {
        "source_symbol_count_matches": same_count,
        "resource_identity_chain_matches": resource_chain_match,
        "symbol_identity_and_visual_fields_match": identity_visual_match,
        "serialized_symbol_offsets_scale_exactly_2x": offsets_double,
        "sprite_cut_rectangles_scale_exactly_2x": rectangles_double,
        "source_png_dimensions_scale_exactly_2x": dimensions_double,
        "native_texture_wrap_codes_match": wraps_match,
        "normalized_uvs_match": uv_match,
        "cpu_xy_geometry_scales_exactly_2x": geometry_double,
        "packet_source_order_matches": source_order_match,
        "rgba_blend_and_winding_metadata_match": color_blend_winding_match,
        "all_links_bounds_and_packet_values_valid": link_bounds_ok,
    }
    return {
        "classification": "private_multisymbol_resolution_pack_parity",
        "direction": med_report["direction"],
        "frame_index": med_report["frame_index"],
        "source_symbol_count": len(med_symbols),
        "screen_med": _pack_summary(med_report),
        "screen_xlarge": _pack_summary(xlarge_report),
        "checks": checks,
        "paired_resolution_parity_verified": all(checks.values()),
        "active_mask_source": "CLI argument or default zero; not recovered from runtime",
        "runtime_active_mask_verified": False,
        "sprite_player_transform_used_identity_for_isolated_test": True,
        "original_runtime_pixel_parity_verified": False,
        "gpu_submission_verified": False,
        "private_resource_details_exported": False,
    }


def audit_private_multisymbol_resolution_parity(
    ipa: Path,
    regions: tuple[tuple[int, int], tuple[int, int]],
    alias: str,
    variant: int,
    direction: str,
    frame_index: int,
    *,
    active_mask: int = 0,
) -> dict:
    """Run the source CLI resolver for both packs and compare private geometry."""
    med_details: list = []
    xlarge_details: list = []
    med_report = audit_private_multisymbol_frame(
        ipa, regions, alias, variant, direction, frame_index,
        active_mask=active_mask, source_screen_group=SCREENS[0],
        _private_details=med_details,
    )
    xlarge_report = audit_private_multisymbol_frame(
        ipa, regions, alias, variant, direction, frame_index,
        active_mask=active_mask, source_screen_group=SCREENS[1],
        _private_details=xlarge_details,
    )
    if len(med_details) != 1 or len(xlarge_details) != 1:
        raise ResolutionParityError("Private resolution details were not collected exactly once")
    if (med_report["direction"] != xlarge_report["direction"]
            or med_report["frame_index"] != xlarge_report["frame_index"]
            or med_report["component_variant_index"] != xlarge_report["component_variant_index"]):
        raise ResolutionParityError("Paired source selections differ")
    return summarize_resolution_parity(
        med_report, xlarge_report, med_details[0], xlarge_details[0],
        active_mask=active_mask,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--region", action="append", required=True, type=_parse_region,
                        help="private byte window START:END; provide exactly two")
    parser.add_argument("--alias", required=True,
                        help="private short alias from local source data")
    parser.add_argument("--variant", required=True, type=int, choices=(0, 1))
    parser.add_argument("--direction", required=True, choices=("east", "west"))
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--active-mask", type=_parse_active_mask, default=0,
                        help="auditor-supplied signed 32-bit mask (decimal or 0x-prefixed)")
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args(argv)
    if len(args.region) != 2:
        parser.error("exactly two --region values are required")
    destination = private_output_path(args.report_out)
    report = audit_private_multisymbol_resolution_parity(
        args.ipa, tuple(args.region), args.alias, args.variant,
        args.direction, args.frame, active_mask=args.active_mask,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("Private paired-resolution frame audit complete; aggregate report saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
