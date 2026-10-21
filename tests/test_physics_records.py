"""Stage141: invented physics record fixtures, never copied iOS bytes."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.physics_records import (
    PhysicsRecordFormatError, audit_private_physics_records,
    parse_physics_structure, summarize_physics_records,
)
from test_shapes import circle, polygon


def text16(value: str) -> bytes:
    data = value.encode("utf-16le")
    return struct.pack("<H", len(data)//2) + data


def record(label="", names=("FakeCircle",), body=None) -> bytes:
    if body is None:
        body = bytes(50)
    assert len(body) == 50
    return (text16(label) + body + struct.pack("<I", len(names))
            + b"".join(text16(value) for value in names))


def fixture(records=None, tail_count=0, opaque=b"") -> bytes:
    if records is None:
        records = [record(names=("FakeCircle",))]
    return (struct.pack("<I",len(records))+b"".join(records)
            +struct.pack("<I",tail_count)+opaque)


def make_ipa(path: Path, *, change_large=False, extra=()):
    rows=[]
    for screen in ("screen-med","screen-xlarge"):
        root=f"Payload/MOTU.app/{screen}/"
        rows.extend([
            (root+"physics_struct/FakeActor.ps2d",fixture([
                record(names=("FakeCircle", "FakePoly")),
                record("FakeJoint",names=("FakePoly",)),
            ],tail_count=2,opaque=b"opaque-tail-not-interpreted")),
            (root+"physics_struct/FakeProp.pstruct2d",
             fixture([record(names=("FakeCircle",))]) +
             (b"BAD" if screen=="screen-xlarge" and change_large else b"")),
            (root+"geometry/FakeCircle.shape",circle()),
            (root+"geometry/FakePoly.shape",polygon()),
        ])
    rows.extend(extra)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as z:
            for name,blob in rows:
                z.writestr(name,blob)


class Stage141RealEnvelopeContractTests(unittest.TestCase):
    def test_one_record_with_zero_footer_exact_eof(self):
        res=parse_physics_structure(fixture())
        self.assertEqual(len(res.records),1)
        self.assertEqual(res.records[0].shape_reference_strings,("FakeCircle",))
        self.assertEqual(res.trailing_group_count,0)
        self.assertEqual(res.trailing_opaque_bytes,0)

    def test_multiple_records_multiple_refs_and_opaque_trailer(self):
        res=parse_physics_structure(fixture([
            record("",("FakeCircle","FakePoly")),
            record("Joint",("FakePoly",)),
        ],tail_count=3,opaque=b"unknown-extra-structure"))
        self.assertEqual(len(res.records),2)
        self.assertEqual(res.records[1].label,"Joint")
        self.assertEqual(res.records[0].shape_reference_strings,
                         ("FakeCircle","FakePoly"))
        self.assertEqual(res.trailing_group_count,3)
        self.assertGreater(res.trailing_opaque_bytes,0)

    def test_fixed_50_bytes_are_opaque_not_runtime_claim(self):
        nonzero=bytes(range(50))
        res=parse_physics_structure(fixture([record(body=nonzero)]))
        self.assertEqual(len(res.records),1)
        summary=summarize_physics_records(
            {"Fake.ps2d":fixture([record(body=nonzero)])},
            {"FakeCircle.shape":circle()})
        self.assertIs(summary["fifty_byte_record_payload_fields_decoded"],False)
        self.assertFalse(summary["source_game_collision_semantics_verified"])

    def test_aggregate_matches_true_candidate_strings_without_names(self):
        phys={
            "FakeActor.ps2d":fixture([
                record(names=("FakeCircle","FakePoly")),
                record("FakeLabel",names=("NotInLibrary",)),
            ],tail_count=1,opaque=b"unknown data"),
            "FakeProp.pstruct2d":fixture([record(names=("FakeCircle",))]),
        }
        shapes={"FakeCircle.shape":circle(),"FakePoly.shape":polygon()}
        report=summarize_physics_records(phys,shapes)
        self.assertEqual(report["parsed_physics_records"],3)
        self.assertEqual(report["length_prefixed_reference_strings"],4)
        self.assertEqual(report["reference_strings_matching_shape_stems"],3)
        self.assertEqual(report["distinct_reference_strings"],3)
        self.assertEqual(report["distinct_matching_shape_stems"],2)
        self.assertEqual(report["files_with_uninterpreted_nonempty_trailer"],1)
        self.assertEqual(report["files_with_empty_opaque_trailer"],1)
        self.assertFalse(report["string_means_runtime_shape_reference_proven"])
        for secret in ("FakeActor","FakeProp","FakeCircle","FakePoly",
                       "FakeLabel","NotInLibrary","unknown data"):
            self.assertNotIn(secret,json.dumps(report))

    def test_reject_nonzero_suffix_after_zero_tail(self):
        with self.assertRaisesRegex(PhysicsRecordFormatError,"trailer"):
            parse_physics_structure(fixture()+b"JUNK")

    def test_reject_nonzero_tail_without_opaque_data(self):
        with self.assertRaisesRegex(PhysicsRecordFormatError,"trailer"):
            parse_physics_structure(fixture(tail_count=4))

    def test_reject_missing_final_tail(self):
        with self.assertRaisesRegex(PhysicsRecordFormatError,"trailer"):
            parse_physics_structure(fixture()[:-4])

    def test_reject_oversized_counts(self):
        with self.assertRaisesRegex(PhysicsRecordFormatError,"record count"):
            parse_physics_structure(struct.pack("<I",100000)+bytes(100))
        data=fixture([record()])
        at=4+2+50
        corrupt=bytearray(data)
        struct.pack_into("<I",corrupt,at,65)
        with self.assertRaisesRegex(PhysicsRecordFormatError,"shape-string count"):
            parse_physics_structure(bytes(corrupt))

    def test_reject_missing_reference_strings(self):
        with self.assertRaisesRegex(PhysicsRecordFormatError,"shape-string count"):
            parse_physics_structure(fixture([record(names=())]))

    def test_reject_truncated_opaque_prefix_and_reference(self):
        full=fixture()
        with self.assertRaises(PhysicsRecordFormatError):
            parse_physics_structure(full[:26])
        # Reference expects 10 UTF-16 code units but not enough data follows.
        raw=bytearray(full)
        struct.pack_into("<H",raw,4+2+50+4,512)
        with self.assertRaises(PhysicsRecordFormatError):
            parse_physics_structure(bytes(raw))

    def test_reject_corrupt_utf16_and_control_chars(self):
        raw=bytearray(fixture([record(label="A")]))
        raw[6:8]=b"\x00\xd8"
        with self.assertRaisesRegex(PhysicsRecordFormatError,"Invalid source UTF-16"):
            parse_physics_structure(bytes(raw))
        with self.assertRaisesRegex(PhysicsRecordFormatError,"control"):
            parse_physics_structure(fixture([record(label="\n")]))

    def test_reject_nonbytes_and_too_short(self):
        for payload in ("not bytes", b"", b"12345"):
            with self.subTest(payload=type(payload).__name__), self.assertRaises(
                    PhysicsRecordFormatError):
                parse_physics_structure(payload)

    def test_original_ios_archive_not_required_for_fake_integration(self):
        with tempfile.TemporaryDirectory() as d:
            ipa=Path(d)/"synthetic.ipa"
            make_ipa(ipa)
            report=audit_private_physics_records(ipa)
        self.assertEqual(report["paired_physics_structures"],2)
        self.assertEqual(report["paired_shape_library_entries"],2)
        self.assertEqual(report["parsed_physics_records"],3)
        self.assertEqual(report["length_prefixed_reference_strings"],4)
        self.assertTrue(report["record_envelope_parse_verified"])
        self.assertFalse(report["ready_for_switch_geometry_import"])

    def test_cross_pack_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ipa=Path(d)/"synthetic.ipa"
            make_ipa(ipa,change_large=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_physics_records(ipa)

    def test_duplicate_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ipa=Path(d)/"synthetic.ipa"
            make_ipa(ipa,extra=[(
                "Payload/MOTU.app/screen-med/physics_struct/FakeActor.ps2d",
                fixture())])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_physics_records(ipa)

    def test_symlinked_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ipa=Path(d)/"synthetic.ipa"
            extras=[]
            for screen in ("screen-med","screen-xlarge"):
                name=f"Payload/MOTU.app/{screen}/physics_struct/Link.ps2d"
                item=ZipInfo(name);item.create_system=3
                item.external_attr=(stat.S_IFLNK|0o777)<<16
                extras.append((item,b"relative"))
            make_ipa(ipa,extra=extras)
            with self.assertRaisesRegex(ValueError,"unsafe"):
                audit_private_physics_records(ipa)

    def test_private_archive_missing(self):
        with self.assertRaisesRegex(ValueError,"Original private IPA not found"):
            audit_private_physics_records(Path("/invalid/owner-archive.ipa"))


if __name__ == "__main__":
    unittest.main()
