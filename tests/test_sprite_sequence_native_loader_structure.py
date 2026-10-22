"""Stage167 original loader shape tests using entirely invented resources."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.sprite_repo_wad_index import SCREENS, SpriteIndexFormatError
from heman_tools.sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from heman_tools.sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD
from heman_tools.sprite_sequence_native_loader_structure import (
    FIXED_SYMBOL_SCALAR_BYTES, FRAME_HEADER_BYTES, _parse_native_sequence,
    summarize_native_sequence_loader_structure,
    audit_private_native_sequence_loader_structure,
)
from test_sprite_repo_wad_index import repository, string


def invented_symbol(name="CutA", *, values=None):
    """76 fixed bytes of invented scalars + UTF-16 name, no original art."""
    head = struct.pack("<2i", 0, 0)
    scalar4 = struct.pack("<4i", 0, 5, 6, 7)
    floats = struct.pack("<6f", *([0.5] * 6))
    final7 = struct.pack("<7i", 0, 0, 0, 0, 0, 0, 0)
    result = head + string(name) + scalar4 + floats + final7
    assert len(result) == 76 + len(string(name))
    return result


def invented_sequence(name, frames, *, loop=0, third=0):
    payload = bytearray(string(name) + struct.pack("<3i", loop,
                                                    len(frames), third))
    for header, switch_bool, symbols in frames:
        payload.extend(struct.pack("<4i", *header))
        payload.extend(struct.pack("<B", switch_bool))
        payload.extend(struct.pack("<i", len(symbols)))
        for item in symbols:
            payload.extend(invented_symbol(item))
    return bytes(payload)


def invented_packs(*, other_resolution_header=False,
                    other_resolution_symbol=False):
    frames = (
        ((1, 40, 1, 0), 0, ("CutA",)),
        ((2, 60, 0, 0), 1, ("AB", "CutB")),
    )
    rows = (
        ("InventedIdle", invented_sequence("InventedIdle", frames)),
        ("InventedEmpty", invented_sequence("InventedEmpty", ())),
        ("InventedNoSymbols", invented_sequence(
            "InventedNoSymbols", (((2, 15, 1, 0), 0, ()),))),
    )
    repos, wads, cuts = {}, {}, {}
    for screen in SCREENS:
        blobs = [record for _, record in rows]
        if screen == SCREENS[1] and other_resolution_header:
            src = blobs[0]
            # Only the first numerical frame field differs, not count,
            # time, serialized name lengths or source record sizes.
            old = struct.pack("<4i", 1, 40, 1, 0)
            new = struct.pack("<4i", 99, 40, 1, 0)
            blobs[0] = src.replace(old, new, 1)
        if screen == SCREENS[1] and other_resolution_symbol:
            blobs[0] = blobs[0].replace(string("CutA"),
                                          string("CutB"), 1)
        offsets = []
        at = 0
        for item in blobs:
            offsets.append(at)
            at += len(item)
        repos[screen] = repository(
            "SpriteSeqData", WAD_PATH,
            tuple(name for name, _ in rows), tuple(offsets),
        )
        wads[screen] = b"".join(blobs)
        cuts[screen] = repository(
            "SpriteCutData", CUT_WAD, ("CutA", "CutB"), (0, 12),
        )
    return repos, wads, cuts


def invented_ipa(path, sources, *, duplicate=False, symlink=False):
    repos, wads, cuts = sources
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(path, "w") as z:
            for screen in SCREENS:
                prefix = "Payload/MOTU.app/" + screen + "/"
                z.writestr(prefix + REPO_PATH, repos[screen])
                z.writestr(prefix + CUT_REPO, cuts[screen])
                if symlink:
                    info = ZipInfo(prefix + WAD_PATH)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    z.writestr(info, wads[screen])
                else:
                    z.writestr(prefix + WAD_PATH, wads[screen])
            if duplicate:
                z.writestr("Payload/MOTU.app/" + SCREENS[0] +
                           "/" + CUT_REPO, b"duplicate")


class Stage167SyntheticNativeSpriteLoader(unittest.TestCase):
    def test_serialized_symbol_fixed_scalar_size(self):
        self.assertEqual(FIXED_SYMBOL_SCALAR_BYTES, 76)
        self.assertEqual(len(invented_symbol("AB")), 82)
        self.assertEqual(len(invented_symbol("CutA")), 86)

    def test_serialized_frame_header_width(self):
        self.assertEqual(FRAME_HEADER_BYTES, 21)

    def test_native_frame_count_is_explicit_signed_integer(self):
        record = invented_sequence("InventedIdle",
                                   (((1, 33, 0, 0), 0, ("CutA",)),))
        parsed = _parse_native_sequence(record)
        self.assertEqual(len(parsed.frames), 1)
        self.assertEqual(parsed.frames[0].numerical_header[1], 33)

    def test_nested_frame_and_symbol_counts(self):
        report = summarize_native_sequence_loader_structure(
            *invented_packs())
        census = report["per_original_resolution_pack"]
        self.assertEqual(census["sequence_records"], 3)
        self.assertEqual(census["frames"], 3)
        self.assertEqual(census["symbols"], 3)
        self.assertEqual(census["zero_frame_records"], 1)
        self.assertEqual(census["zero_symbol_frames"], 1)

    def test_registered_and_unregistered_source_names_separate(self):
        report = summarize_native_sequence_loader_structure(
            *invented_packs())
        census = report["per_original_resolution_pack"]
        self.assertEqual(census["indexed_symbol_references"], 2)
        self.assertEqual(census["unindexed_symbol_references"], 1)
        self.assertEqual(census["unindexed_two_unit_names"], 1)

    def test_symbol_count_one_but_sequence_two_frames(self):
        parsed = _parse_native_sequence(invented_sequence(
            "InventedIdle", (
                ((1, 11, 0, 0), 1, ("CutA",)),
                ((2, 12, 0, 0), 0, ()),
            )))
        self.assertEqual(len(parsed.frames), 2)
        self.assertEqual(tuple(len(x.symbol_names) for x in parsed.frames),
                         (1, 0))

    def test_zero_frames_have_exact_header_end(self):
        raw = invented_sequence("InventedEmpty", ())
        self.assertEqual(len(raw), len(string("InventedEmpty")) + 12)
        self.assertEqual(_parse_native_sequence(raw).frames, ())

    def test_loop_and_extra_header_are_not_frame_counts(self):
        parsed = _parse_native_sequence(invented_sequence(
            "InventedIdle", (((1, 17, 0, 0), 0, ("CutA",)),),
            loop=-1, third=70,
        ))
        self.assertEqual(parsed.loop_field, -1)
        self.assertEqual(parsed.third_field, 70)
        self.assertEqual(len(parsed.frames), 1)

    def test_internal_resource_key_not_required_to_be_in_cut_registry(self):
        parsed = _parse_native_sequence(invented_sequence(
            "InventedIdle", (((1, 17, 0, 0), 0, ("ZZ",)),)))
        self.assertEqual(parsed.frames[0].symbol_names, ("ZZ",))

    def test_original_time_field_is_second_frame_integer(self):
        parsed = _parse_native_sequence(invented_sequence(
            "InventedIdle", (((1, 63, 0, 0), 0, ("CutA",)),)))
        self.assertEqual(parsed.frames[0].numerical_header[1], 63)

    def test_fabricated_resolution_headers_can_differ(self):
        report = summarize_native_sequence_loader_structure(
            *invented_packs(other_resolution_header=True))
        equal = report["paired_pack_equalities"]
        self.assertEqual(equal["all_frame_numeric_headers_equal"], 2)
        self.assertEqual(equal["per_frame_symbol_counts_equal"], 3)
        self.assertEqual(equal["per_frame_symbol_names_equal"], 3)

    def test_fabricated_name_difference_detected_without_publishing_name(self):
        report = summarize_native_sequence_loader_structure(
            *invented_packs(other_resolution_symbol=True))
        self.assertEqual(report["paired_pack_equalities"][
            "per_frame_symbol_names_equal"], 2)

    def test_fake_synthetic_native_loader_accepts_both_screens(self):
        result = summarize_native_sequence_loader_structure(
            *invented_packs())
        self.assertTrue(result["complete_exact_EOF_native_load_order_verified"])
        self.assertEqual(result["paired_pack_equalities"][
            "per_frame_symbol_counts_equal"], 3)

    def test_one_unexpected_terminal_byte_fails_exact_eof(self):
        raw = invented_sequence("InventedIdle", (((1, 13, 0, 0), 0,
                                                  ("CutA",)),))
        with self.assertRaisesRegex(SpriteIndexFormatError,
                                    "unread trailing bytes"):
            _parse_native_sequence(raw + b"\x00")

    def test_truncated_scalar_field_fails(self):
        raw = invented_sequence("InventedIdle", (((1, 13, 0, 0), 0,
                                                  ("CutA",)),))
        with self.assertRaisesRegex(SpriteIndexFormatError, "Truncated"):
            _parse_native_sequence(raw[:-3])

    def test_negative_frame_count_fails(self):
        raw = string("InventedIdle") + struct.pack("<3i", 0, -1, 0)
        with self.assertRaisesRegex(SpriteIndexFormatError,
                                    "Invalid native frame count"):
            _parse_native_sequence(raw)

    def test_excessive_symbol_count_fails(self):
        raw = (string("InventedIdle") + struct.pack("<3i", 0, 1, 0)
               + struct.pack("<4i", 1, 15, 0, 0)
               + b"\x00" + struct.pack("<i", 3001))
        with self.assertRaisesRegex(SpriteIndexFormatError,
                                    "Invalid native frame symbol count"):
            _parse_native_sequence(raw)

    def test_control_character_in_symbol_name_fails(self):
        raw = invented_sequence("InventedIdle",
                                (((1, 15, 0, 0), 0, ("CutA",)),))
        token = string("CutA")
        raw = raw.replace(token, string("\x01utA"), 1)
        with self.assertRaisesRegex(SpriteIndexFormatError,
                                    "Control character"):
            _parse_native_sequence(raw)

    def test_private_names_not_in_aggregate_report(self):
        report = summarize_native_sequence_loader_structure(
            *invented_packs())
        encoded = json.dumps(report, sort_keys=True)
        for name in ("InventedIdle", "CutA", "CutB", "ZZ",
                     "private_original_sprite_bytes"):
            self.assertNotIn(name, encoded)
        self.assertFalse(report["rendered_frame_timing_units_calibrated"])
        self.assertFalse(report[
            "runtime_texture_mapping_and_collision_bindings_verified"])
        self.assertFalse(report["safe_to_publish_original_graphics"])

    def test_owner_ipa_fixture_roundtrip(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "invented.ipa"
            invented_ipa(path, invented_packs())
            report = audit_private_native_sequence_loader_structure(path)
        self.assertEqual(report["per_original_resolution_pack"]["frames"], 3)

    def test_duplicate_archive_index_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "invented.ipa"
            invented_ipa(path, invented_packs(), duplicate=True)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                audit_private_native_sequence_loader_structure(path)

    def test_selected_wad_symlink_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "invented.ipa"
            invented_ipa(path, invented_packs(), symlink=True)
            with self.assertRaisesRegex(ValueError, "unsafe selected"):
                audit_private_native_sequence_loader_structure(path)

    def test_missing_owner_ipa_rejected(self):
        with self.assertRaisesRegex(ValueError, "Owner-private original IPA"):
            audit_private_native_sequence_loader_structure(
                Path("/not-present/private-source.ipa")
            )


if __name__ == "__main__":
    unittest.main()
