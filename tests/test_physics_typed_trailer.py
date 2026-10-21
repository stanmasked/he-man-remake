"""Stage147: fictional-only tests of observed *structural* discriminator framing.

No original iOS names, bytes, shapes, physics geometry or gameplay traces.
"""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipInfo

from heman_tools.physics_typed_trailer import (
    VARIANT_OPAQUE_SIZES, parse_typed_trailer_counts,
    summarize_typed_trailer_framing, audit_private_typed_trailers,
)
from heman_tools.physics_records import PhysicsRecordFormatError
from test_physics_records import fixture, record, make_ipa, text16


def mock_tail(rows):
    return b"".join(
        text16(label) + struct.pack("<I", variant) +
        bytes([variant + 1]) * VARIANT_OPAQUE_SIZES[variant]
        for label, variant in rows
    )


def source_with_tail(rows, label="FakeMain"):
    return fixture([record(label, names=("FakeShape",))],
                   tail_count=len(rows), opaque=mock_tail(rows))


class Stage147TypedPhysicsTrailerTests(unittest.TestCase):
    def test_three_variants_exact_eof_and_aggregate_counts(self):
        payload = mock_tail([("FakeA",0),("FakeB",1),("FakeC",2)])
        self.assertEqual(parse_typed_trailer_counts(payload,3),
                         {0:1,1:1,2:1})

    def test_variants_repeated_in_different_orders(self):
        example=[("One",2),("Two",0),("Three",2),("",1),("Four",0)]
        self.assertEqual(parse_typed_trailer_counts(mock_tail(example),5),
                         {0:2,1:1,2:2})

    def test_single_variant_0_full_record(self):
        self.assertEqual(parse_typed_trailer_counts(mock_tail([("",0)]),1),
                         {0:1,1:0,2:0})

    def test_single_variant_1_full_record(self):
        self.assertEqual(parse_typed_trailer_counts(mock_tail([("Example",1)]),1),
                         {0:0,1:1,2:0})

    def test_single_variant_2_full_record(self):
        self.assertEqual(parse_typed_trailer_counts(mock_tail([("Example",2)]),1),
                         {0:0,1:0,2:1})

    def test_unicode_code_units_do_not_shift_record_boundary(self):
        rows=[("Fictional-☃",0),("🦖",2)]
        self.assertEqual(sum(parse_typed_trailer_counts(
            mock_tail(rows),2).values()),2)

    def test_wrong_discriminator_fails_closed(self):
        altered=bytearray(mock_tail([("Fake",0)]))
        at=len(text16("Fake"))
        struct.pack_into("<I",altered,at,3)
        with self.assertRaisesRegex(PhysicsRecordFormatError,"Unrecognized"):
            parse_typed_trailer_counts(bytes(altered),1)

    def test_record_payload_short_read_fails_closed(self):
        for variant in VARIANT_OPAQUE_SIZES:
            with self.subTest(variant=variant):
                broken=mock_tail([("X",variant)])[:-1]
                with self.assertRaisesRegex(PhysicsRecordFormatError,"Truncated"):
                    parse_typed_trailer_counts(broken,1)

    def test_extra_tail_byte_rejected_not_skipped(self):
        source=mock_tail([("X",0)])+b"\xff"
        with self.assertRaisesRegex(PhysicsRecordFormatError,"unconsumed"):
            parse_typed_trailer_counts(source,1)

    def test_declared_record_count_too_small_or_large_rejected(self):
        source=mock_tail([("X",0),("Y",1)])
        with self.assertRaises(PhysicsRecordFormatError):
            parse_typed_trailer_counts(source,1)
        with self.assertRaises(PhysicsRecordFormatError):
            parse_typed_trailer_counts(source,3)

    def test_corrupt_utf16_label_rejected(self):
        source=bytearray(mock_tail([("X",0)]))
        source[2:4]=b"\x00\xd8"
        with self.assertRaisesRegex(PhysicsRecordFormatError,"UTF-16"):
            parse_typed_trailer_counts(bytes(source),1)

    def test_truncated_label_length_rejected(self):
        source=bytearray(mock_tail([("X",0)]))
        struct.pack_into("<H",source,0,300)
        with self.assertRaises(PhysicsRecordFormatError):
            parse_typed_trailer_counts(bytes(source),1)

    def test_missing_variant_four_bytes_rejected(self):
        source=text16("Name")+b"\0\0"
        with self.assertRaisesRegex(PhysicsRecordFormatError,"discriminator"):
            parse_typed_trailer_counts(source,1)

    def test_zero_bool_and_excess_count_guards(self):
        for count in (0,513,True,-1,1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                parse_typed_trailer_counts(mock_tail([("X",0)]),count)
        for source in ("str",b"",b"\0"*8193):
            with self.subTest(source_type=type(source).__name__), self.assertRaises(ValueError):
                parse_typed_trailer_counts(source,1)

    def test_aggregate_keeps_source_opaque_and_forbids_runtime_claims(self):
        docs={
            "HiddenEntity.ps2d":source_with_tail([("SecretTail",0),("SecretLink",2)]),
            "HiddenProp.pstruct2d":fixture([record()],tail_count=0),
        }
        report=summarize_typed_trailer_framing(docs)
        self.assertEqual(report["paired_physics_source_files_examined"],2)
        self.assertEqual(report["source_files_with_typed_trailer"],1)
        self.assertEqual(report["source_files_with_no_trailer"],1)
        self.assertEqual(report["declared_trailer_items_fully_framed"],2)
        self.assertEqual(report["variant_0_item_count"],1)
        self.assertEqual(report["variant_2_item_count"],1)
        self.assertTrue(report["observed_structural_variant_framing_verified"])
        for flag in (
            "discriminator_original_runtime_meaning_verified",
            "original_ios_joint_collider_or_material_semantics_verified",
            "safe_for_automatic_switch_geometry_import"):
            self.assertFalse(report[flag])
        result=json.dumps(report)
        for secret in ("HiddenEntity","HiddenProp","SecretTail",
                       "SecretLink","FakeShape","FakeMain","0x"):
            self.assertNotIn(secret,result)

    def test_fabricated_ipa_paired_resource_parsing(self):
        with TemporaryDirectory() as d:
            from zipfile import ZipFile
            p=Path(d)/"fake.ipa"
            with ZipFile(p,"w") as z:
                for screen in ("screen-med","screen-xlarge"):
                    prefix="Payload/MOTU.app/"+screen+"/physics_struct/"
                    z.writestr(prefix+"FakePlayer.ps2d",
                               source_with_tail([("FakeOne",0),("FakeTwo",1),("",2)]))
            result=audit_private_typed_trailers(p)
        self.assertEqual(result["declared_trailer_items_fully_framed"],3)
        self.assertEqual(result["source_files_with_typed_trailer"],1)

    def test_original_source_duplicate_zip_entries_rejected(self):
        with TemporaryDirectory() as d:
            from zipfile import ZipFile
            p=Path(d)/"fake.ipa"
            name="Payload/MOTU.app/screen-med/physics_struct/Fake.ps2d"
            with ZipFile(p,"w") as z:
                z.writestr(name,source_with_tail([("A",0)]))
                z.writestr(name,source_with_tail([("B",1)]))
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_typed_trailers(p)

    def test_paired_source_byte_divergence_rejected(self):
        with TemporaryDirectory() as d:
            from zipfile import ZipFile
            p=Path(d)/"fake.ipa"
            with ZipFile(p,"w") as z:
                for screen,kind in (("screen-med",0),("screen-xlarge",1)):
                    z.writestr("Payload/MOTU.app/"+screen+
                               "/physics_struct/Fake.ps2d",
                               source_with_tail([("Fake",kind)]))
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_typed_trailers(p)

    def test_paired_symlink_rejected(self):
        with TemporaryDirectory() as d:
            from zipfile import ZipFile
            p=Path(d)/"fake.ipa"
            with ZipFile(p,"w") as z:
                for screen in ("screen-med","screen-xlarge"):
                    entry=ZipInfo("Payload/MOTU.app/"+screen+
                                  "/physics_struct/Fake.ps2d")
                    entry.create_system=3
                    entry.external_attr=(stat.S_IFLNK | 0o777)<<16
                    z.writestr(entry,b"relative")
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_typed_trailers(p)

    def test_owner_original_not_available_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner-private"):
            audit_private_typed_trailers(Path("/missing/owner.ipa"))


if __name__ == "__main__":
    unittest.main()
