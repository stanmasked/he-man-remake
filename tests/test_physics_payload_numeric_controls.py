"""Stage148: strictly invented numeric payloads, never source iOS game bytes."""
from __future__ import annotations

import json
import math
import stat
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.physics_payload_numeric_controls import (
    _classify_float32, _typed_payloads,
    summarize_private_payload_numeric_controls,
    audit_private_payload_numeric_controls,
)
from heman_tools.physics_records import PhysicsRecordFormatError
from test_physics_records import fixture, record, text16


def fake_payload(variant: int, *, scale: float = 1.0) -> bytes:
    if variant == 0:
        return b"\xff" + struct.pack("<8f", 0,scale,2*scale,3*scale,
                                     4*scale,-scale,6*scale,7*scale)
    if variant == 1:
        return b"\xff" + struct.pack("<6f", 0,scale,2*scale,3*scale,
                                     4*scale,-scale)
    if variant == 2:
        return b"\xff\xaa" + struct.pack("<8f", 0,scale,2*scale,3*scale,
                                         4*scale,-scale,6*scale,7*scale)
    raise ValueError("Fictional generator supports only the three observed codes")


def fake_tail(items):
    return b"".join(text16("FictionalLabel") +
                    struct.pack("<I", variant) + fake_payload(variant, scale=scale)
                    for variant,scale in items)


def fake_physics(items):
    return fixture([record("FictionalMain",names=("FictionalShape",))],
                   tail_count=len(items),opaque=fake_tail(items))


def fake_sources():
    return {
        "FictionalActor.ps2d":fake_physics([(0,1),(1,2),(2,3)]),
        "FictionalDecoration.pstruct2d":fake_physics([(0,4),(1,5),(2,6)]),
        "FictionalEmpty.ps2d":fixture([record()]),
    }


def fake_zip(path, *, divergent=False, extras=()):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as z:
            for screen in ("screen-med","screen-xlarge"):
                prefix=f"Payload/MOTU.app/{screen}/physics_struct/"
                for name,blob in fake_sources().items():
                    if divergent and screen=="screen-xlarge" and name=="FictionalActor.ps2d":
                        blob = fake_physics([(0,7),(1,2),(2,3)])
                    z.writestr(prefix+name,blob)
            for entry,raw in extras:
                z.writestr(entry,raw)


class Stage148PayloadNumericControlsTests(unittest.TestCase):
    def test_synthetic_three_variant_source_aggregate(self):
        result=summarize_private_payload_numeric_controls(fake_sources())
        self.assertEqual(result["paired_original_physics_files_examined"],3)
        self.assertEqual(result["source_files_with_typed_record_trailers"],2)
        self.assertEqual(result["typed_payload_record_count"],6)
        for kind,size in ((0,33),(1,25),(2,34)):
            v=result["variants"]["variant_"+str(kind)]
            self.assertEqual(v["opaque_payload_byte_count"],size)
            self.assertEqual(v["sampled_typed_records"],2)
        self.assertFalse(result["automatic_original_geometry_import_permitted"])

    def test_variant0_offset_one_little_endian_recovers_all_fictional_floats(self):
        report=summarize_private_payload_numeric_controls(fake_sources())
        c=report["variants"]["variant_0"]["float32_alignment_and_byte_order_controls"]
        probe=c["offset_1_little_endian"]
        self.assertEqual(probe["candidate_lanes_per_record"],8)
        self.assertEqual(probe["examined_candidate_float32_bits"],16)
        self.assertEqual(probe["in_heuristic_window_including_zero"],16)
        self.assertEqual(probe["not_finite"],0)

    def test_variant1_offset_one_little_endian_recovers_all_fictional_floats(self):
        report=summarize_private_payload_numeric_controls(fake_sources())
        c=report["variants"]["variant_1"]["float32_alignment_and_byte_order_controls"]
        probe=c["offset_1_little_endian"]
        self.assertEqual(probe["candidate_lanes_per_record"],6)
        self.assertEqual(probe["examined_candidate_float32_bits"],12)
        self.assertEqual(probe["in_heuristic_window_including_zero"],12)

    def test_variant2_offset_two_little_endian_recovers_all_fictional_floats(self):
        report=summarize_private_payload_numeric_controls(fake_sources())
        c=report["variants"]["variant_2"]["float32_alignment_and_byte_order_controls"]
        probe=c["offset_2_little_endian"]
        self.assertEqual(probe["candidate_lanes_per_record"],8)
        self.assertEqual(probe["examined_candidate_float32_bits"],16)
        self.assertEqual(probe["in_heuristic_window_including_zero"],16)

    def test_all_four_alignment_offsets_and_both_byte_orders_are_reported(self):
        out=summarize_private_payload_numeric_controls(fake_sources())
        for kind in range(3):
            c=out["variants"]["variant_"+str(kind)][
                "float32_alignment_and_byte_order_controls"]
            self.assertEqual(len(c),8)
            for offset in range(4):
                for order in ("little_endian","big_endian"):
                    self.assertIn(f"offset_{offset}_{order}",c)

    def test_float_classification_excludes_extreme_and_nonfinite_values(self):
        self.assertEqual(_classify_float32(0),"exact_zero")
        self.assertEqual(_classify_float32(-0.0),"exact_zero")
        self.assertEqual(_classify_float32(5),"nonzero_within_window")
        self.assertEqual(_classify_float32(-10000),"nonzero_within_window")
        self.assertEqual(_classify_float32(1e-9),"nonzero_below_window")
        self.assertEqual(_classify_float32(-1e7),"nonzero_above_window")
        self.assertEqual(_classify_float32(float("nan")),"not_finite")
        self.assertEqual(_classify_float32(float("inf")),"not_finite")

    def test_wrong_endian_is_never_assumed_original_field_schema(self):
        report=summarize_private_payload_numeric_controls(fake_sources())
        ctrl=report["variants"]["variant_0"][
            "float32_alignment_and_byte_order_controls"]
        self.assertLess(ctrl["offset_1_big_endian"]["in_heuristic_window_including_zero"],
                        ctrl["offset_1_little_endian"]["in_heuristic_window_including_zero"])
        self.assertFalse(report["byte_alignment_or_endianness_of_original_numeric_fields_verified"])

    def test_distinct_payload_patterns_and_varying_bytes_are_only_aggregates(self):
        report=summarize_private_payload_numeric_controls(fake_sources())
        for kind in range(3):
            data=report["variants"]["variant_"+str(kind)]
            self.assertEqual(data["distinct_payload_bit_patterns"],2)
            self.assertEqual(
                data["byte_positions_identical_across_variant_records"] +
                data["byte_positions_varying_across_variant_records"],
                data["opaque_payload_byte_count"])

    def test_strict_rewalk_returns_private_blobs_only_in_memory(self):
        data=fake_tail([(0,1),(1,2),(2,3)])
        grouped=_typed_payloads(data,3)
        self.assertEqual([len(grouped[x]) for x in range(3)],[1,1,1])
        self.assertEqual([len(grouped[x][0]) for x in range(3)],[33,25,34])

    def test_truncated_payload_cannot_be_accepted_as_float_data(self):
        fake=fake_tail([(0,1)])
        with self.assertRaises(PhysicsRecordFormatError):
            _typed_payloads(fake[:-1],1)

    def test_wrong_item_count_or_extra_bytes_cannot_be_accepted(self):
        fake=fake_tail([(0,1),(2,2)])
        with self.assertRaises(PhysicsRecordFormatError):
            _typed_payloads(fake,1)
        with self.assertRaises(PhysicsRecordFormatError):
            _typed_payloads(fake+b"EXTRA",2)

    def test_unrecognized_original_variant_fails_closed(self):
        fake=bytearray(fake_tail([(0,1)]))
        struct.pack_into("<I",fake,len(text16("FictionalLabel")),999)
        with self.assertRaisesRegex(PhysicsRecordFormatError,"Unrecognized"):
            _typed_payloads(bytes(fake),1)

    def test_missing_variant_rejected_by_full_three_variant_study(self):
        with self.assertRaisesRegex(ValueError,"Missing required variant"):
            summarize_private_payload_numeric_controls({
                "Fiction.ps2d":fake_physics([(0,1),(1,1)])
            })

    def test_corrupt_main_record_is_rejected_before_any_guess(self):
        sources=fake_sources()
        sources["FictionalActor.ps2d"]=b"\xff"*120
        with self.assertRaises(ValueError):
            summarize_private_payload_numeric_controls(sources)

    def test_empty_or_untrusted_member_names_and_payload_types_rejected(self):
        for files in ({},
                      {"../bad.ps2d":fake_physics([(0,1)])},
                      {"Unsafe.exe":fake_physics([(0,1)])},
                      {"Unsafe.ps2d":"not bytes"}):
            with self.subTest(files=tuple(files)),self.assertRaises(ValueError):
                summarize_private_payload_numeric_controls(files)

    def test_original_resource_identifiers_and_numbers_not_exported(self):
        report=json.dumps(summarize_private_payload_numeric_controls(fake_sources()))
        for forbidden in ("FictionalActor","FictionalDecoration","FictionalLabel",
                          "FictionalShape","FictionalMain","geometry/",
                          "physics_struct/"):
            self.assertNotIn(forbidden,report)
        self.assertFalse(json.loads(report)["original_strings_raw_bytes_coordinates_and_file_hashes_in_report"])

    def test_private_dual_screen_fake_zip_success(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa"
            fake_zip(p)
            report=audit_private_payload_numeric_controls(p)
        self.assertEqual(report["typed_payload_record_count"],6)
        self.assertFalse(report["original_game_physics_and_switch_runtime_parity_verified"])

    def test_private_dual_screen_byte_divergence_fails_closed(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa"
            fake_zip(p,divergent=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_payload_numeric_controls(p)

    def test_duplicate_zip_resource_fails_closed(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa"
            fake_zip(p,extras=[(
                "Payload/MOTU.app/screen-med/physics_struct/FictionalActor.ps2d",
                fake_physics([(0,1)]))])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_payload_numeric_controls(p)

    def test_symlinked_paired_zip_resources_fails_closed(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa"
            entries=[]
            for screen in ("screen-med","screen-xlarge"):
                i=ZipInfo(f"Payload/MOTU.app/{screen}/physics_struct/Link.ps2d")
                i.create_system=3
                i.external_attr=(stat.S_IFLNK|0o777)<<16
                entries.append((i,b"relative target"))
            fake_zip(p,extras=entries)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_payload_numeric_controls(p)

    def test_owner_private_ipa_missing_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Private original iOS IPA not found"):
            audit_private_payload_numeric_controls(Path("/missing-private-original.ipa"))


if __name__ == "__main__":
    unittest.main()
