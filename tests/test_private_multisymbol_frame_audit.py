"""Synthetic-only tests for the Stage204 multi-Symbol audit CLI helpers."""
from __future__ import annotations

import argparse
import json
import io
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from PIL import Image

from heman_tools.physics_shape_census import PREFIX, SCREENS
from heman_tools.private_multisymbol_frame_audit import (
    _aggregate_symbol_transform_summary,
    _checked_png_dimensions,
    _parse_active_mask,
    _parse_region,
    _require_rectangle_in_bounds,
    audit_private_multisymbol_frame,
    main,
)
from heman_tools.private_single_symbol_frame_decoder import PrivateFrameDecodeError
from heman_tools.private_multisymbol_resolution_parity import (
    audit_private_multisymbol_resolution_parity,
)
from heman_tools.native_render_state_contract import (
    GL_LINEAR, GL_LINEAR_MIPMAP_NEAREST, GL_NEAREST, NATIVE_DEFAULT_PLAYER_BLEND,
    NativeRenderStateError, decode_texture_filter_mode, resolve_texture_sampling_state,
)
from heman_tools.texture_sampling_mode_census import audit_private_texture_sampling_modes
from heman_tools.private_cpu_frame_preview import (
    PrivateCPUFramePreviewError,
    render_private_cpu_frame_preview,
)
from heman_tools.symbol_frame_render_plan import PlayerTransform


def png_bytes(size=(8, 8), *, transparent_border=False):
    image = Image.new(
        "RGBA", size, (0, 0, 0, 0) if transparent_border else (12, 34, 56, 255)
    )
    if transparent_border:
        from PIL import ImageDraw
        scale = size[0] // 16
        draw = ImageDraw.Draw(image)
        draw.rectangle((2 * scale, 2 * scale, 6 * scale - 1, 6 * scale - 1),
                       fill=(12, 34, 56, 255))
        draw.rectangle((10 * scale, 2 * scale, 14 * scale - 1, 6 * scale - 1),
                       fill=(12, 34, 56, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _string(value):
    raw = value.encode("utf-16le")
    return struct.pack("<H", len(raw) // 2) + raw


def _indexed_repo(label, rows, target):
    out = bytearray(_string(label) + struct.pack("<HI", 0, len(rows)))
    for key, offset in rows:
        out += _string(key) + struct.pack("<I", 0) + _string(target) + struct.pack("<I", offset)
    return bytes(out)


def _sequence_record(key, symbols, scale_xs=None, *, offset_scale=1):
    if scale_xs is None:
        scale_xs = (1.0,) * len(symbols)
    if len(scale_xs) != len(symbols):
        raise ValueError("scale_xs must parallel the source Symbols")
    out = bytearray(_string(key) + struct.pack("<iii", 0, 1, 0))
    out += struct.pack("<4i", 0, 100, 0, 0) + b"\x00" + struct.pack("<i", len(symbols))
    for (name, offset_x, mask), scale_x in zip(symbols, scale_xs):
        out += struct.pack("<ii", 0, 0) + _string(name)
        out += struct.pack("<4i", 0, 0, offset_x * offset_scale, 12 * offset_scale)
        out += struct.pack("<6f", 1, 1, 1, 1, scale_x, 1)
        out += struct.pack("<7i", 0, 0, 0, 0, -1, -1, mask)
    return bytes(out)


def _cut_record(name, texture, rectangle):
    return (_string(name) + _string(texture) + struct.pack("<I", 1)
            + struct.pack("<5i", 0, *rectangle))


def _image_repo():
    return (_string("ImageData") + struct.pack("<HI", 0, 1)
            + _string("SyntheticImage") + struct.pack("<I", 1)
            + _string("/textures/synthetic.png") + struct.pack("<I", 0))


def _synthetic_multisymbol_ipa(path, *, symbols=(("SyntheticCutA", 10, 0),
                                                  ("SyntheticCutB", 30, 0)),
                               rectangles=((0, 0, 8, 8), (8, 0, 8, 8)),
                               scale_xs=None,
                               resolution_scale=2,
                               filter_mode=0,
                               xlarge_filter_mode=None,
                               alpha_transform_flag=0,
                               transparent_border=False,
                               png_size=(16, 16)):
    east_key, west_key = "syntheticIdle.e", "syntheticIdle.w"
    east_record = _sequence_record(east_key, symbols, scale_xs)
    west_record = _sequence_record(west_key, symbols, scale_xs)
    east_record_xlarge = _sequence_record(east_key, symbols, scale_xs,
                                          offset_scale=resolution_scale)
    west_record_xlarge = _sequence_record(west_key, symbols, scale_xs,
                                          offset_scale=resolution_scale)
    sequence_wad_by_screen = {
        SCREENS[0]: east_record + west_record,
        SCREENS[1]: east_record_xlarge + west_record_xlarge,
    }
    sequence_repo = _indexed_repo(
        "SpriteSeqData",
        ((east_key, 0), (west_key, len(east_record))),
        "sprite/SpriteSeqData.wad",
    )

    cut_records = tuple(_cut_record(name, "SyntheticTexture", rect)
                        for (name, _, _), rect in zip(symbols, rectangles))
    cut_records_xlarge = tuple(
        _cut_record(name, "SyntheticTexture", tuple(value * resolution_scale for value in rect))
        for (name, _, _), rect in zip(symbols, rectangles)
    )
    cut_wad_by_screen = {
        SCREENS[0]: b"".join(cut_records),
        SCREENS[1]: b"".join(cut_records_xlarge),
    }
    cut_offsets = []
    at = 0
    for record in cut_records:
        cut_offsets.append(at)
        at += len(record)
    cut_repo = _indexed_repo(
        "SpriteCutData",
        tuple((symbols[i][0], cut_offsets[i]) for i in range(len(symbols))),
        "sprite/SpriteResData.wad",
    )

    scalar_med = bytearray(13)
    scalar_med[5] = alpha_transform_flag
    scalar_med[10] = 0
    scalar_med[11] = 0
    scalar_med[6:10] = struct.pack("<i", filter_mode)
    scalar_med[12] = 0
    scalar_xlarge = bytearray(scalar_med)
    if xlarge_filter_mode is not None:
        scalar_xlarge[6:10] = struct.pack("<i", xlarge_filter_mode)
        scalar_xlarge[12] = 0
    texture_record_by_screen = {
        SCREENS[0]: _string("SyntheticTexture") + bytes(scalar_med)
                    + _string("") + _string("SyntheticImage"),
        SCREENS[1]: _string("SyntheticTexture") + bytes(scalar_xlarge)
                    + _string("") + _string("SyntheticImage"),
    }
    texture_repo = _indexed_repo(
        "TextureData", (("SyntheticTexture", 0),), "textureData/TextureData.wad"
    )
    image_repo = _image_repo()
    go = (_string("syntheticIdle") + _string(east_key) + _string(west_key)
          + _string("syntheticOther") + _string(east_key) + _string(west_key))
    split = len(_string("syntheticIdle") + _string(east_key) + _string(west_key))
    with ZipFile(path, "w") as archive:
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            scale = 1 if screen == SCREENS[0] else resolution_scale
            image = png_bytes((16 * scale, 16 * scale),
                              transparent_border=transparent_border)
            archive.writestr(root + "go/default", go)
            archive.writestr(root + "meta/SpriteSeqData.repo", sequence_repo)
            archive.writestr(root + "sprite/SpriteSeqData.wad", sequence_wad_by_screen[screen])
            archive.writestr(root + "meta/SpriteCutData.repo", cut_repo)
            archive.writestr(root + "sprite/SpriteResData.wad", cut_wad_by_screen[screen])
            archive.writestr(root + "meta/TextureData.repo", texture_repo)
            archive.writestr(root + "textureData/TextureData.wad", texture_record_by_screen[screen])
            archive.writestr(root + "meta/ImageData.repo", image_repo)
            archive.writestr(root + "textures/synthetic.png", image)
    return ((0, split), (split, len(go)))


class PrivateMultiSymbolFrameAuditTests(unittest.TestCase):
    def test_region_parser_requires_positive_interval(self):
        self.assertEqual(_parse_region("10:20"), (10, 20))
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_region("20:20")
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_region("20:10")

    def test_active_mask_parser_accepts_decimal_and_hex(self):
        self.assertEqual(_parse_active_mask("4"), 4)
        self.assertEqual(_parse_active_mask("0x10"), 16)
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_active_mask("0x100000000")

    def test_region_and_mask_parsers_reject_malformed_text(self):
        for value in ("", "10", "a:b", "10:20:30"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                _parse_region(value)
        for value in ("", "mask", "0xzz"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                _parse_active_mask(value)

    def test_png_dimensions_helper_validates_full_png_and_rectangle(self):
        dims = _checked_png_dimensions(png_bytes((16, 8)), (2, 1, 3, 4))
        self.assertEqual(dims, (16, 8))
        with self.assertRaises(PrivateFrameDecodeError):
            _checked_png_dimensions(png_bytes((8, 8)), (7, 7, 2, 2))
        with self.assertRaises(PrivateFrameDecodeError):
            _checked_png_dimensions(b"not png", (0, 0, 1, 1))

    def test_cached_dimensions_still_validate_each_rectangle(self):
        _require_rectangle_in_bounds((1, 2, 3, 4), (8, 8))
        with self.assertRaisesRegex(PrivateFrameDecodeError, "PNG bounds"):
            _require_rectangle_in_bounds((7, 7, 2, 2), (8, 8))

    def test_zero_width_and_negative_origin_fail_closed(self):
        for rectangle in ((0, 0, 0, 1), (-1, 0, 1, 1), (0, -1, 1, 1)):
            with self.subTest(rectangle=rectangle), self.assertRaises(PrivateFrameDecodeError):
                _require_rectangle_in_bounds(rectangle, (8, 8))

    def test_original_ipa_cli_path_resolves_and_assembles_synthetic_multisymbol_frame(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            regions = _synthetic_multisymbol_ipa(ipa)
            report_path = Path.cwd() / "local_reports" / "stage204-multisymbol-integration-test.json"
            try:
                result = audit_private_multisymbol_frame(
                    ipa, regions, "syntheticIdle", 0, "east", 0, active_mask=0
                )
                self.assertEqual(result["source_symbol_count"], 2)
                self.assertEqual(result["resolved_symbol_count"], 2)
                self.assertEqual(result["cpu_frame_packet_count"], 2)
                self.assertEqual(result["cpu_frame_packet_vertex_count"], 8)
                self.assertEqual(result["cpu_frame_packet_uv_pair_count"], 8)
                self.assertTrue(result["cpu_frame_packet_source_order_preserved"])
                self.assertTrue(result["all_source_pngs_validated"])
                self.assertFalse(result["runtime_active_mask_verified"])
                self.assertFalse(result["original_runtime_pixel_parity_verified"])
                self.assertNotIn("SyntheticCut", str(result))
                self.assertNotIn("/textures/", str(result))

                self.assertEqual(main([
                    "--ipa", str(ipa),
                    "--region", f"{regions[0][0]}:{regions[0][1]}",
                    "--region", f"{regions[1][0]}:{regions[1][1]}",
                    "--alias", "syntheticIdle", "--variant", "0",
                    "--direction", "east", "--frame", "0",
                    "--active-mask", "0", "--report-out", str(report_path),
                ]), 0)
                import json
                saved = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["cpu_frame_packet_count"], 2)
                self.assertNotIn("SyntheticCut", json.dumps(saved))
            finally:
                report_path.unlink(missing_ok=True)

    def test_paired_resolution_audit_confirms_uv_and_geometry_scaling(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "paired-resolution.ipa"
            regions = _synthetic_multisymbol_ipa(ipa)
            report = audit_private_multisymbol_resolution_parity(
                ipa, regions, "syntheticIdle", 0, "east", 0, active_mask=0
            )
            self.assertTrue(report["paired_resolution_parity_verified"])
            self.assertTrue(all(report["checks"].values()))
            self.assertEqual(report["screen_med"]["cpu_frame_packet_count"], 2)
            self.assertEqual(report["screen_xlarge"]["cpu_frame_packet_count"], 2)
            self.assertTrue(report["screen_med"]["all_source_pngs_validated"])
            self.assertTrue(report["screen_xlarge"]["all_source_pngs_validated"])
            self.assertFalse(report["original_runtime_pixel_parity_verified"])
            self.assertFalse(report["private_resource_details_exported"])

    def test_paired_resolution_audit_rejects_unscaled_xlarge_pack(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "unscaled.ipa"
            regions = _synthetic_multisymbol_ipa(ipa, resolution_scale=1)
            report = audit_private_multisymbol_resolution_parity(
                ipa, regions, "syntheticIdle", 0, "east", 0, active_mask=0
            )
            self.assertFalse(report["paired_resolution_parity_verified"])
            self.assertFalse(report["checks"]["serialized_symbol_offsets_scale_exactly_2x"])
            self.assertFalse(report["checks"]["sprite_cut_rectangles_scale_exactly_2x"])
            self.assertFalse(report["checks"]["source_png_dimensions_scale_exactly_2x"])
            self.assertFalse(report["checks"]["cpu_xy_geometry_scales_exactly_2x"])
            self.assertTrue(report["checks"]["normalized_uvs_match"])
            self.assertFalse(report["original_runtime_pixel_parity_verified"])
            self.assertNotIn("SyntheticCutA", json.dumps(report))

    def test_native_texture_filter_contract_and_full_pack_census(self):
        nearest = bytes(13)
        linear = bytearray(13)
        linear[6:10] = struct.pack("<i", 1)
        linear[12] = 0
        self.assertEqual(decode_texture_filter_mode(nearest), 0)
        self.assertEqual(decode_texture_filter_mode(bytes(linear)), 1)
        self.assertEqual(resolve_texture_sampling_state(0).min_filter, GL_NEAREST)
        self.assertEqual(resolve_texture_sampling_state(0).mag_filter, GL_NEAREST)
        self.assertFalse(resolve_texture_sampling_state(0).generate_mipmaps)
        linear_state = resolve_texture_sampling_state(1)
        self.assertEqual((linear_state.min_filter, linear_state.mag_filter),
                         (GL_LINEAR, GL_LINEAR))
        self.assertFalse(linear_state.generate_mipmaps)
        mip_state = resolve_texture_sampling_state(2)
        self.assertEqual(mip_state.min_filter, GL_LINEAR_MIPMAP_NEAREST)
        self.assertTrue(mip_state.generate_mipmaps)
        self.assertEqual(NATIVE_DEFAULT_PLAYER_BLEND, (1, 0x0303))
        invalid = bytearray(13)
        invalid[6:10] = struct.pack("<i", 3)
        with self.assertRaises(NativeRenderStateError):
            decode_texture_filter_mode(bytes(invalid))

        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "sampling-census.ipa"
            _synthetic_multisymbol_ipa(ipa)
            report = audit_private_texture_sampling_modes(ipa)
            self.assertTrue(report["paired_sampling_metadata_match"])
            self.assertEqual(report["texture_record_count_per_pack"], 1)
            self.assertEqual(report["per_pack"]["screen-med"]["filter_mode_counts"],
                             {"nearest": 1, "linear": 0, "linear_mipmap_nearest": 0})
            self.assertFalse(report["original_runtime_pixel_parity_verified"])

    def test_census_accepts_matching_linear_selector_without_claiming_all_nearest(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "linear-sampling-census.ipa"
            _synthetic_multisymbol_ipa(ipa, filter_mode=1)
            report = audit_private_texture_sampling_modes(ipa)
            self.assertTrue(report["paired_sampling_metadata_match"])
            self.assertFalse(report["all_source_textures_use_nearest_filtering_without_mipmaps"])
            self.assertEqual(report["per_pack"]["screen-med"]["filter_mode_counts"],
                             {"nearest": 0, "linear": 1, "linear_mipmap_nearest": 0})

    def test_paired_resolution_audit_rejects_filter_mode_mismatch(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "filter-mismatch.ipa"
            regions = _synthetic_multisymbol_ipa(ipa, xlarge_filter_mode=1)
            report = audit_private_multisymbol_resolution_parity(
                ipa, regions, "syntheticIdle", 0, "east", 0, active_mask=0
            )
            self.assertFalse(report["paired_resolution_parity_verified"])
            self.assertFalse(report["checks"]["native_texture_filter_modes_match"])
            self.assertTrue(report["checks"]["native_texture_wrap_codes_match"])
            self.assertNotIn("SyntheticTexture", json.dumps(report))

    def test_private_cpu_preview_decodes_png_and_renders_linear_frame(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "cpu-preview.ipa"
            regions = _synthetic_multisymbol_ipa(
                ipa, filter_mode=1, alpha_transform_flag=1,
                transparent_border=True,
            )
            report, rendered = render_private_cpu_frame_preview(
                ipa, regions, "syntheticIdle", 0, "east", 0,
                screen=SCREENS[0], active_mask=0,
            )
            self.assertEqual(report["source_symbol_count"], 2)
            self.assertEqual(report["cpu_frame_packet_count"], 2)
            self.assertEqual(
                report["symbol_local_transform_summary"]["symbol_count"], 2
            )
            self.assertFalse(
                report["symbol_local_transform_summary"]["raw_transform_values_exported"]
            )
            self.assertEqual(report["native_texture_filter_mode_counts_by_unique_texture"],
                             {"nearest": 0, "linear": 1, "unsupported_mipmap": 0})
            self.assertEqual(report["unique_textures_with_alpha_transform_enabled"], 1)
            self.assertTrue(report["all_payloads_use_png_path"])
            self.assertGreater(rendered.pixel_samples, 0)
            self.assertTrue(any(rendered.rgba[3::4]))
            self.assertEqual((rendered.width, rendered.height),
                             (report["output_width"], report["output_height"]))
            self.assertTrue(report["output_crop_applied"])
            self.assertLess(report["output_width"], report["render_canvas_width"])
            self.assertLess(report["output_height"], report["render_canvas_height"])
            self.assertFalse(report["gpu_submission_verified"])
            self.assertFalse(report["original_runtime_pixel_parity_verified"])
            self.assertFalse(report["private_resource_details_exported"])

    def test_synthetic_player_scale_changes_preview_geometry_not_source_status(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic-player-scale.ipa"
            regions = _synthetic_multisymbol_ipa(ipa)
            baseline, first = render_private_cpu_frame_preview(
                ipa, regions, "syntheticIdle", 0, "east", 0,
            )
            scaled, second = render_private_cpu_frame_preview(
                ipa, regions, "syntheticIdle", 0, "east", 0,
                player_transform=PlayerTransform(scale_x=1.5),
            )
            self.assertEqual(baseline["player_transform"], "identity assumption")
            self.assertFalse(baseline["synthetic_player_transform_applied"])
            self.assertTrue(scaled["synthetic_player_transform_applied"])
            self.assertFalse(scaled["runtime_player_transform_grounded"])
            self.assertFalse(scaled["player_transform_values_exported"])
            self.assertFalse(scaled["original_runtime_pixel_parity_verified"])
            self.assertNotEqual(first.width, second.width)
            self.assertGreater(second.width, first.width)
            self.assertEqual(baseline["texture_binding_count"], scaled["texture_binding_count"])
            self.assertEqual(baseline["source_symbol_count"], scaled["source_symbol_count"])
            self.assertIn("synthetic nonidentity", scaled["player_transform"])
            self.assertNotIn("1.5", json.dumps(scaled))

    def test_translation_is_recentered_and_cannot_prove_scene_position(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "translation-only.ipa"
            regions = _synthetic_multisymbol_ipa(ipa)
            ordinary, first = render_private_cpu_frame_preview(
                ipa, regions, "syntheticIdle", 0, "west", 0,
            )
            shifted, second = render_private_cpu_frame_preview(
                ipa, regions, "syntheticIdle", 0, "west", 0,
                player_transform=PlayerTransform(translation_x=64, translation_y=32),
            )
            self.assertEqual((first.width, first.height), (second.width, second.height))
            self.assertEqual(first.rgba, second.rgba)
            self.assertTrue(shifted["source_translation_canceled_by_bounds_projection"])
            self.assertTrue(shifted["synthetic_player_transform_applied"])
            self.assertFalse(shifted["full_scene_placement_verified"])
            self.assertFalse(shifted["original_runtime_pixel_parity_verified"])
            self.assertEqual(ordinary["source_symbol_count"], shifted["source_symbol_count"])

    def test_player_transform_type_is_validated_before_private_ipa_read(self):
        with self.assertRaisesRegex(PrivateCPUFramePreviewError, "validated PlayerTransform"):
            render_private_cpu_frame_preview(
                Path("/unavailable/source.ipa"), ((0, 1), (1, 2)),
                "syntheticIdle", 0, "east", 0,
                player_transform={"translation_x": 2},
            )

    def test_private_cpu_preview_rejects_unimplemented_mipmap_sampling(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "mipmap-preview.ipa"
            regions = _synthetic_multisymbol_ipa(ipa, filter_mode=2)
            with self.assertRaises(PrivateCPUFramePreviewError):
                render_private_cpu_frame_preview(
                    ipa, regions, "syntheticIdle", 0, "east", 0,
                    screen=SCREENS[0], active_mask=0,
                )

    def test_negative_horizontal_scale_is_accepted_as_finite_mirrored_geometry(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "mirrored.ipa"
            regions = _synthetic_multisymbol_ipa(ipa, scale_xs=(1.0, -1.0))
            report = audit_private_multisymbol_frame(
                ipa, regions, "syntheticIdle", 0, "west", 0, active_mask=0
            )
            self.assertEqual(report["source_symbol_count"], 2)
            self.assertEqual(report["cpu_frame_packet_count"], 2)
            self.assertEqual(report["cpu_frame_packet_vertex_count"], 8)
            self.assertTrue(report["cpu_frame_packet_finite"])
            self.assertTrue(report["native_winding_flag_computed"])
            self.assertTrue(report["cpu_frame_packet_source_order_preserved"])

    def test_multisymbol_cli_applies_explicit_mask_without_renumbering(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "masked.ipa"
            regions = _synthetic_multisymbol_ipa(
                ipa, symbols=(("SyntheticCutA", 10, 0), ("SyntheticCutB", 30, 4))
            )
            report = audit_private_multisymbol_frame(
                ipa, regions, "syntheticIdle", 0, "west", 0, active_mask=4
            )
            self.assertEqual(report["source_symbol_count"], 2)
            self.assertEqual(report["cpu_frame_packet_count"], 1)
            self.assertEqual(report["masked_symbol_count"], 1)
            self.assertTrue(report["cpu_frame_packet_source_order_preserved"])

    def test_both_source_regions_must_fit_the_go_record(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "bad-region.ipa"
            regions = _synthetic_multisymbol_ipa(ipa)
            bad_regions = (regions[0], (regions[1][0], regions[1][1] + 1))
            with self.assertRaisesRegex(PrivateFrameDecodeError, "exceeds the source GO data"):
                audit_private_multisymbol_frame(
                    ipa, bad_regions, "syntheticIdle", 0, "east", 0
                )

    def test_multisymbol_cli_rejects_out_of_bounds_late_symbol(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "out-of-bounds.ipa"
            regions = _synthetic_multisymbol_ipa(
                ipa, rectangles=((0, 0, 8, 8), (15, 15, 8, 8))
            )
            with self.assertRaises(PrivateFrameDecodeError):
                audit_private_multisymbol_frame(
                    ipa, regions, "syntheticIdle", 0, "east", 0
                )



class SymbolTransformSummaryTests(unittest.TestCase):
    def test_summary_counts_local_transforms_without_exporting_raw_values(self):
        symbols = [
            {
                "serialized_fields": (0, 90, 5, -2),
                "transform_values": (0.5, 1.0, 1.0, 1.0, 2.0, -1.0),
                "serialized_tail": (1, 2, 3, 4, 1, 1, 0),
            },
            {
                "serialized_fields": (1, 0, 0, 0),
                "transform_values": (1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
                "serialized_tail": (1, 2, 1, 5, -1, -1, 2),
            },
        ]
        summary = _aggregate_symbol_transform_summary(symbols)
        self.assertEqual(summary["symbol_count"], 2)
        self.assertEqual(summary["nonzero_rotation_count"], 1)
        self.assertEqual(summary["nonzero_offset_x_count"], 1)
        self.assertEqual(summary["nonzero_offset_y_count"], 1)
        self.assertEqual(summary["non_unit_scale_x_count"], 1)
        self.assertEqual(summary["non_unit_scale_y_count"], 1)
        self.assertEqual(summary["negative_scale_x_count"], 0)
        self.assertEqual(summary["negative_scale_y_count"], 1)
        self.assertEqual(summary["zero_scale_x_count"], 0)
        self.assertEqual(summary["zero_scale_y_count"], 0)
        self.assertEqual(summary["non_default_color_multiplier_count"], 1)
        self.assertEqual(summary["nonzero_symbol_mask_count"], 1)
        self.assertEqual(summary["resolved_blend_override_count"], 1)
        self.assertEqual(summary["tween_selector_counts"]["rotation"], {"2": 2})
        self.assertEqual(summary["tween_selector_counts"]["scale_x_y"], {"1": 1, "3": 1})
        self.assertEqual(summary["player_wide_transform_used"],
                         "identity assumption for isolated CPU preview")
        self.assertFalse(summary["raw_transform_values_exported"])
        self.assertNotIn("serialized_fields", summary)
        self.assertNotIn("transform_values", summary)

    def test_summary_rejects_incomplete_transform_record(self):
        with self.assertRaises(PrivateFrameDecodeError):
            _aggregate_symbol_transform_summary([{
                "serialized_fields": (0, 0, 0, 0),
                "transform_values": (1.0, 1.0),
                "serialized_tail": (1, 2, 3, 4, -1, -1, 0),
            }])


if __name__ == "__main__":
    unittest.main()
