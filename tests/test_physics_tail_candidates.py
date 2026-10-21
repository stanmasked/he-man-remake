"""Stage143: intentionally fictional UTF-16 trailer framing, no original IPA."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.physics_tail_candidates import (
    LAYOUT_NAME_THEN_OPAQUE, LAYOUT_OPAQUE_THEN_NAME,
    candidate_tail_boundaries, summarize_tail_boundary_candidates,
    audit_private_candidate_trailers,
)
from heman_tools.physics_records import PhysicsRecordFormatError
from test_physics_records import fixture, record, make_ipa, text16


def two_named_groups(*, padding=5):
    return (text16("FakeFirst") + b"\xff" * padding
            + text16("FakeSecond") + b"\xff" * padding)


def mock_files():
    return {
        "FakeActor.ps2d": fixture(
            [record(names=("FakeCircle",))],
            tail_count=2,
            opaque=two_named_groups(padding=5)),
        "FakeProp.pstruct2d": fixture(
            [record(names=("FakeCircle",))]),
    }


class Stage143ExactBoundaryModels(unittest.TestCase):
    def test_repeated_label_then_fixed_padding_exact_eof_candidate(self):
        candidates = candidate_tail_boundaries(two_named_groups(), 2)
        self.assertIn((LAYOUT_NAME_THEN_OPAQUE, 5), candidates)

    def test_fixed_padding_then_labels_exact_eof_candidate(self):
        payload = (b"\xff"*7 + text16("One")
                   + b"\xff"*7 + text16("Two"))
        candidate = candidate_tail_boundaries(payload, 2)
        self.assertIn((LAYOUT_OPAQUE_THEN_NAME, 7), candidate)

    def test_trailing_extra_byte_invalidates_original_candidate(self):
        payload = two_named_groups(padding=5)
        candidates = candidate_tail_boundaries(payload+b"\xee", 2)
        self.assertNotIn((LAYOUT_NAME_THEN_OPAQUE, 5), candidates)

    def test_truncated_last_padding_invalidates_original_candidate(self):
        payload = two_named_groups(padding=5)
        candidates = candidate_tail_boundaries(payload[:-1], 2)
        self.assertNotIn((LAYOUT_NAME_THEN_OPAQUE, 5), candidates)

    def test_bad_second_label_not_accepted_just_from_first_prefix(self):
        raw = text16("PlausibleStart") + b"\xff"*50
        candidates = candidate_tail_boundaries(raw, 2)
        self.assertFalse(any(kind == LAYOUT_NAME_THEN_OPAQUE for kind, _ in candidates))

    def test_one_group_possible_but_explicitly_non_discriminating(self):
        source={"One.ps2d":fixture(
            [record()], tail_count=1,
            opaque=text16("FakeLabel")+b"\xff"*6)}
        result=summarize_tail_boundary_candidates(source)
        self.assertEqual(result["single_group_trailers_non_discriminating"],1)
        self.assertGreater(result["total_candidate_framings"],0)
        self.assertFalse(result["original_trailer_layout_verified"])

    def test_all_zero_bytes_can_be_ambiguous_and_must_not_be_promoted(self):
        # Two empty candidate labels and 8 unknown bytes per item,
        # both directions fit; this is an ambiguous shape of bytes.
        source={"F.ps2d":fixture(
            [record()],tail_count=2,opaque=bytes(20))}
        result=summarize_tail_boundary_candidates(source)
        self.assertGreaterEqual(result["files_with_ambiguous_multiple_candidates"],1)
        self.assertEqual(result["multi_group_trailers_with_exactly_one_candidate"],0)
        self.assertFalse(result["original_trailer_item_semantics_verified"])

    def test_unparseable_data_returns_zero_candidates_not_false_success(self):
        source={"F.ps2d":fixture(
            [record()],tail_count=2,opaque=b"\xff"*20)}
        result=summarize_tail_boundary_candidates(source)
        self.assertEqual(result["files_with_no_complete_candidate"],1)
        self.assertEqual(result["total_candidate_framings"],0)

    def test_duplicate_layout_with_zero_padding_is_counted_once(self):
        candidate = candidate_tail_boundaries(
            text16("NameA")+text16("NameB"),2,max_fixed_bytes=0)
        self.assertEqual(candidate,((LAYOUT_NAME_THEN_OPAQUE,0),))

    def test_bounded_width_rejects_out_of_range_requested_search(self):
        for limit in (-1, 97, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                candidate_tail_boundaries(two_named_groups(),2,
                                          max_fixed_bytes=limit)

    def test_group_count_and_trailer_bytes_validate_fail_closed(self):
        for groups in (0, -1, 513, True, 1.0):
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                candidate_tail_boundaries(b"\x00\x00", groups)
        for payload in (b"", "not bytes", b"0"*8193):
            with self.subTest(payload_type=type(payload).__name__), self.assertRaises(
                    ValueError):
                candidate_tail_boundaries(payload,2)

    def test_end_to_end_aggregate_counts_have_no_private_identifiers(self):
        report=summarize_tail_boundary_candidates(mock_files())
        self.assertEqual(report["source_physics_files_examined"],2)
        self.assertEqual(report["nonempty_trailer_files"],1)
        self.assertEqual(report["declared_trailer_groups"],2)
        self.assertEqual(report["multi_group_trailers_examined"],1)
        self.assertEqual(report["single_group_trailers_non_discriminating"],0)
        self.assertGreater(report["total_candidate_framings"],0)
        self.assertFalse(report["safe_for_switch_geometry_import"])
        serialized=json.dumps(report)
        for secret in ("FakeActor","FakeProp","FakeCircle","FakeFirst",
                       "FakeSecond","OpaqueFakeLabel","png","shape_filename"):
            self.assertNotIn(secret,serialized)

    def test_missing_source_and_bad_path_rejected(self):
        with self.assertRaisesRegex(ValueError,"Missing or excessive"):
            summarize_tail_boundary_candidates({})
        with self.assertRaisesRegex(ValueError,"Invalid private source"):
            summarize_tail_boundary_candidates({
                "../unsafe.ps2d": fixture([record()])})

    def test_existing_physics_envelope_malformed_is_rejected(self):
        file=fixture([record()],tail_count=1,opaque=b"fail")
        with self.assertRaises(PhysicsRecordFormatError):
            summarize_tail_boundary_candidates({"F.ps2d":file[:-6]})

    def test_synthetic_original_archive_reads_source_free_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            ipa=Path(directory)/"fake.ipa"
            make_ipa(ipa)
            result=audit_private_candidate_trailers(ipa)
        self.assertEqual(result["source_physics_files_examined"],2)
        self.assertEqual(result["nonempty_trailer_files"],1)
        self.assertEqual(result["declared_trailer_groups"],2)
        self.assertFalse(result["original_trailer_layout_verified"])

    def test_archive_duplicate_and_screen_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            ipa=Path(directory)/"fake.ipa"
            make_ipa(ipa,change_large=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_candidate_trailers(ipa)
            make_ipa(ipa,extra=[(
                "Payload/MOTU.app/screen-med/physics_struct/FakeActor.ps2d",
                fixture([record()]))])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_candidate_trailers(ipa)

    def test_paired_symlinked_resource_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ipa=Path(directory)/"fake.ipa"
            rows=[]
            for screen in ("screen-med","screen-xlarge"):
                entry=ZipInfo(f"Payload/MOTU.app/{screen}/physics_struct/Link.ps2d")
                entry.create_system=3
                entry.external_attr=(stat.S_IFLNK | 0o777) << 16
                rows.append((entry,b"relative.file"))
            make_ipa(ipa,extra=rows)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_candidate_trailers(ipa)

    def test_no_original_archive_fails(self):
        with self.assertRaisesRegex(ValueError,"Privately held original IPA not found"):
            audit_private_candidate_trailers(Path("/missing-private-original.ipa"))


if __name__ == "__main__":
    unittest.main()
