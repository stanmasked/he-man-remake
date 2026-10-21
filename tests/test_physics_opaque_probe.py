"""Stage142 source-free tests: all physics bytes are deliberately fabricated."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.physics_opaque_probe import (
    audit_private_physics_opaque,
    summarize_opaque_parameter_evidence,
)
from heman_tools.physics_records import PhysicsRecordFormatError
from test_physics_records import record, fixture, make_ipa, text16


def synthetic_sources():
    return {
        "FakeActor.ps2d": fixture([
            record("FakeLabel",names=("FakeA",), body=bytes(50)),
            record(names=("FakeB",), body=bytes([1])*50),
        ],tail_count=2,opaque=text16("FakeTail")+b"other opaque"),
        "FakeOther.pstruct2d": fixture([
            record(names=("FakeA",), body=bytes(50)),
        ]),
    }


class Stage142OpaqueEvidenceTests(unittest.TestCase):
    def test_identical_and_different_opaque_blocks_counted_without_bytes(self):
        x=summarize_opaque_parameter_evidence(synthetic_sources())
        self.assertEqual(x["physics_resources_examined"],2)
        self.assertEqual(x["opaque_50_byte_blocks_examined"],3)
        self.assertEqual(x["distinct_50_byte_block_patterns"],2)
        self.assertEqual(x["50_byte_positions_varying_across_records"],50)
        self.assertEqual(x["50_byte_positions_constant_across_records"],0)
        self.assertEqual(x["50_byte_blocks_entirely_zero"],2)
        self.assertFalse(x["opaque_50_byte_parameter_fields_decoded"])

    def test_one_unknown_tail_counted_without_group_record_parsing(self):
        x=summarize_opaque_parameter_evidence(synthetic_sources())
        self.assertEqual(x["resources_with_nonzero_trailer_count"],1)
        self.assertEqual(x["declared_unknown_trailer_group_total"],2)
        self.assertEqual(x["nonzero_trailers_with_candidate_initial_utf16_prefix"],1)
        self.assertEqual(x["candidate_initial_utf16_labels_nonempty"],1)
        self.assertFalse(x["unknown_trailer_group_record_boundaries_decoded"])

    def test_empty_candidate_prefix_counted(self):
        data={"F.ps2d":fixture(
            [record()],
            tail_count=1,
            opaque=struct.pack("<H",0)+bytes(38)
        )}
        x=summarize_opaque_parameter_evidence(data)
        self.assertEqual(x["candidate_initial_utf16_labels_empty"],1)
        self.assertEqual(x["candidate_initial_utf16_labels_nonempty"],0)

    def test_unknown_non_utf16_tail_remains_unknown_not_a_parser_error(self):
        data={"F.ps2d":fixture(
            [record()],
            tail_count=1,
            opaque=struct.pack("<H",65535)+b"\xFF"*6
        )}
        x=summarize_opaque_parameter_evidence(data)
        self.assertEqual(x["nonzero_trailers_with_candidate_initial_utf16_prefix"],0)
        self.assertEqual(x["declared_unknown_trailer_group_total"],1)

    def test_all_zero_payloads_stay_uninterpreted(self):
        x=summarize_opaque_parameter_evidence({"F.ps2d":fixture([record()])})
        self.assertEqual(x["distinct_50_byte_block_patterns"],1)
        self.assertEqual(x["50_byte_positions_varying_across_records"],0)
        self.assertEqual(x["50_byte_positions_constant_across_records"],50)
        self.assertEqual(x["50_byte_blocks_entirely_zero"],1)

    def test_counter_report_contains_no_source_identifiers_or_opaque_data(self):
        text=json.dumps(summarize_opaque_parameter_evidence(synthetic_sources()))
        for secret in ("FakeActor","FakeOther","FakeTail","FakeLabel",
                       "FakeA","FakeB","other opaque","FF FF"):
            self.assertNotIn(secret,text)

    def test_unknown_trailer_length_guard_propagates_fail_closed(self):
        bad=fixture([record()],tail_count=1,opaque=bytes(8193))
        with self.assertRaisesRegex(PhysicsRecordFormatError,"opaque physics trailer"):
            summarize_opaque_parameter_evidence({"F.ps2d":bad})

    def test_early_truncation_cannot_be_misread_as_valid_source(self):
        bad=fixture([record()])
        with self.assertRaises(PhysicsRecordFormatError):
            summarize_opaque_parameter_evidence({"F.ps2d":bad[:-5]})

    def test_zero_trailer_cannot_have_extra_bytes(self):
        with self.assertRaisesRegex(PhysicsRecordFormatError,"trailer"):
            summarize_opaque_parameter_evidence({
                "F.ps2d":fixture([record()])+b"hidden fixture bytes"})

    def test_empty_input_or_invalid_source_name_fails(self):
        with self.assertRaisesRegex(ValueError,"Missing or excessive"):
            summarize_opaque_parameter_evidence({})
        with self.assertRaisesRegex(ValueError,"Invalid private"):
            summarize_opaque_parameter_evidence({"../bad.ps2d":fixture([record()])})

    def test_both_synthetic_resolution_packs_integrate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            make_ipa(path)
            x=audit_private_physics_opaque(path)
        self.assertEqual(x["physics_resources_examined"],2)
        self.assertEqual(x["opaque_50_byte_blocks_examined"],3)
        self.assertEqual(x["resources_with_nonzero_trailer_count"],1)
        self.assertFalse(x["switch_collision_import_allowed"])

    def test_mismatched_resolution_pack_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            make_ipa(path,change_large=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_physics_opaque(path)

    def test_duplicate_archive_entry_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            make_ipa(path,extra=[
                ("Payload/MOTU.app/screen-med/physics_struct/FakeActor.ps2d",
                 fixture([record()]))
            ])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_physics_opaque(path)

    def test_selected_symlink_rejected_after_paired_resource_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            links=[]
            for pack in ("screen-med","screen-xlarge"):
                info=ZipInfo(f"Payload/MOTU.app/{pack}/physics_struct/Link.ps2d")
                info.create_system=3
                info.external_attr=(stat.S_IFLNK|0o777)<<16
                links.append((info,b"relative"))
            make_ipa(path,extra=links)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_physics_opaque(path)

    def test_missing_original_private_ipa_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner private original IPA missing"):
            audit_private_physics_opaque(Path("/no-such-path/owner.ipa"))


if __name__ == "__main__":
    unittest.main()
