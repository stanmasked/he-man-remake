"""Stage149: fabricated-only float hypotheses; no commercial iOS data."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.physics_payload_dedup_controls import (
    numeric_candidate_summary,
    summarize_duplicate_aware_numeric_controls,
    audit_private_duplicate_aware_numeric_controls,
)
from test_physics_payload_numeric_controls import (
    fake_sources, fake_payload, fake_physics, fake_zip,
)


class Stage149DuplicateAwareControlsTests(unittest.TestCase):
    def test_fabricated_three_variant_counts_and_duplicates(self):
        report=summarize_duplicate_aware_numeric_controls(fake_sources())
        self.assertEqual(report["original_physics_source_files_examined"],3)
        self.assertEqual(report["physics_files_with_typed_trailer"],2)
        self.assertEqual(report["typed_trailer_record_count"],6)
        for variant in range(3):
            v=report["variants"]["variant_"+str(variant)]
            self.assertEqual(v["total_record_occurrences"],2)
            self.assertEqual(v["distinct_payload_patterns"],2)
            self.assertEqual(v["duplicate_record_occurrences"],0)
            self.assertEqual(len(v["comparisons"]),8)
        self.assertFalse(report["original_float32_numeric_field_layout_verified"])
        self.assertFalse(report["allow_automatic_original_geometry_import"])

    def test_duplicate_occurrences_must_not_overweight_unique_evidence(self):
        sources={
            "FakeOne.ps2d":fake_physics([(0,1.0)]*7+[(1,2.0),(2,3.0)]),
            "FakeTwo.pstruct2d":fake_physics([(0,4.0),(1,5.0),(2,6.0)]),
        }
        rep=summarize_duplicate_aware_numeric_controls(sources)
        v=rep["variants"]["variant_0"]
        self.assertEqual(v["total_record_occurrences"],8)
        self.assertEqual(v["distinct_payload_patterns"],2)
        self.assertEqual(v["duplicate_record_occurrences"],6)
        x=v["comparisons"]["offset_1_little_endian"]
        self.assertEqual(x["all_record_occurrences"]["sampled_payloads"],8)
        self.assertEqual(x["distinct_payload_patterns_only"]["sampled_payloads"],2)
        self.assertEqual(x["distinct_payload_patterns_only"][
            "nonzero_within_window"],14)

    def test_zeros_do_not_count_as_numeric_evidence(self):
        payload=b"\x00"*33
        score=numeric_candidate_summary([payload,payload],
                                         offset=1,endian="<")
        self.assertEqual(score["exact_zero"],16)
        self.assertEqual(score["nonzero_within_window"],0)
        self.assertEqual(score["lanes_with_any_nonzero_in_heuristic_window"],0)
        self.assertEqual(score["lanes_with_distinct_nonzero_in_heuristic_window"],0)

    def test_subnormal_candidates_excluded_from_positive_signal(self):
        payload=b"\xff"+struct.pack("<8I",*[1]*8)
        score=numeric_candidate_summary([payload],offset=1,endian="<")
        self.assertEqual(score["nonzero_below_window"],8)
        self.assertEqual(score["nonzero_within_window"],0)

    def test_fictional_nonzero_floats_identified_without_field_claim(self):
        payload=fake_payload(0,scale=1.0)
        score=numeric_candidate_summary([payload],offset=1,endian="<")
        self.assertEqual(score["sampled_payloads"],1)
        self.assertEqual(score["candidate_lanes_per_payload"],8)
        self.assertEqual(score["nonzero_within_window"],7)
        self.assertEqual(score["exact_zero"],1)
        self.assertEqual(score["lanes_with_any_nonzero_in_heuristic_window"],7)

    def test_diverse_lanes_require_different_nonzero_candidate_bits(self):
        sample=[fake_payload(0,scale=1),fake_payload(0,scale=1),
                fake_payload(0,scale=2)]
        score=numeric_candidate_summary(sample,offset=1,endian="<")
        self.assertEqual(score["lanes_with_any_nonzero_in_heuristic_window"],7)
        self.assertEqual(score["lanes_with_distinct_nonzero_in_heuristic_window"],7)

    def test_repeated_identical_nonzero_does_not_imply_diverse(self):
        sample=[fake_payload(0,scale=1)]*10
        score=numeric_candidate_summary(sample,offset=1,endian="<")
        self.assertEqual(score["lanes_with_any_nonzero_in_heuristic_window"],7)
        self.assertEqual(score["lanes_with_distinct_nonzero_in_heuristic_window"],0)

    def test_little_endian_candidate_compared_to_big_endian_baseline(self):
        report=summarize_duplicate_aware_numeric_controls(fake_sources())
        v=report["variants"]["variant_0"]
        candidates=v["comparisons"]
        self.assertGreater(candidates["offset_1_little_endian"][
            "distinct_payload_patterns_only"]["nonzero_within_window"],
            candidates["offset_1_big_endian"][
            "distinct_payload_patterns_only"]["nonzero_within_window"])
        self.assertTrue(v["difference_is_not_field_identification"])

    def test_all_four_offsets_and_both_endian_orders_present(self):
        report=summarize_duplicate_aware_numeric_controls(fake_sources())
        for variant in range(3):
            controls=report["variants"]["variant_"+str(variant)]["comparisons"]
            self.assertEqual(set(controls),{
                f"offset_{offset}_{order}"
                for offset in range(4)
                for order in ("little_endian","big_endian")})

    def test_alternative_alignment_yields_different_candidate_lanes(self):
        x=numeric_candidate_summary([fake_payload(0)],offset=1,endian="<")
        y=numeric_candidate_summary([fake_payload(0)],offset=3,endian="<")
        self.assertEqual(x["candidate_lanes_per_payload"],8)
        self.assertEqual(y["candidate_lanes_per_payload"],7)

    def test_nan_and_infinity_never_count_as_finite_signal(self):
        payload=b"\xff"+struct.pack("<8f",
            float("nan"),float("inf"),float("-inf"),1,0,0,0,0)
        score=numeric_candidate_summary([payload],offset=1,endian="<")
        self.assertEqual(score["not_finite"],3)
        self.assertEqual(score["nonzero_within_window"],1)
        self.assertEqual(score["exact_zero"],4)

    def test_invalid_payload_sizes_and_types_fail_closed(self):
        for items in ([],["not-bytes"],[b"a"*3],[b"a"*65],
                      [b"a"*8,b"a"*9]):
            with self.subTest(items=repr(items)[:50]),self.assertRaises(ValueError):
                numeric_candidate_summary(items,offset=0,endian="<")

    def test_invalid_offset_endianness_fail_closed(self):
        for offset,order in ((-1,"<"),(4,"<"),(True,"<"),
                             (1,">>"),(1,"little"),(1,42)):
            with self.subTest(offset=offset,order=order),self.assertRaises(ValueError):
                numeric_candidate_summary([fake_payload(0)],offset=offset,
                                          endian=order)

    def test_missing_variants_rejected_rather_than_downgraded(self):
        with self.assertRaisesRegex(ValueError,"Missing or malformed"):
            summarize_duplicate_aware_numeric_controls({
                "Fake.ps2d":fake_physics([(0,1.0)])})

    def test_bad_physics_envelope_rejected_before_candidate_decoding(self):
        with self.assertRaises(ValueError):
            summarize_duplicate_aware_numeric_controls({
                "Fake.ps2d":b"\xff"*60})

    def test_invalid_filename_or_payload_type_rejected(self):
        for sources in ({},{"../Bad.ps2d":fake_physics([(0,1)])},
                        {"Bad.exe":fake_physics([(0,1)])},
                        {"Bad.ps2d":"text"}):
            with self.subTest(keys=tuple(sources)),self.assertRaises(ValueError):
                summarize_duplicate_aware_numeric_controls(sources)

    def test_report_contains_no_fictional_source_strings_or_binary_values(self):
        result=json.dumps(summarize_duplicate_aware_numeric_controls(fake_sources()))
        for forbidden in ("FictionalActor","FictionalDecoration","FictionalLabel",
                          "FictionalShape","geometry/","physics_struct/"):
            self.assertNotIn(forbidden,result)
        self.assertNotIn("payload_position_",result)
        self.assertFalse(json.loads(result)[
            "source_payload_bytes_string_names_offsets_hashes_in_report"])

    def test_fabricated_paired_ipa_integration(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa";fake_zip(p)
            report=audit_private_duplicate_aware_numeric_controls(p)
        self.assertEqual(report["typed_trailer_record_count"],6)

    def test_mismatched_original_resolution_pack_fails_closed(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa";fake_zip(p,divergent=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_duplicate_aware_numeric_controls(p)

    def test_duplicate_zip_member_fails_closed(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa"
            fake_zip(p,extras=[(
                "Payload/MOTU.app/screen-med/physics_struct/FictionalActor.ps2d",
                fake_physics([(0,1)]))])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_duplicate_aware_numeric_controls(p)

    def test_paired_symlinked_member_fails_closed(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa"
            entries=[]
            for screen in ("screen-med","screen-xlarge"):
                i=ZipInfo(f"Payload/MOTU.app/{screen}/physics_struct/Link.ps2d")
                i.create_system=3
                i.external_attr=(stat.S_IFLNK|0o777)<<16
                entries.append((i,b"relative"))
            fake_zip(p,extras=entries)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_duplicate_aware_numeric_controls(p)

    def test_missing_owner_ipa_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA not found"):
            audit_private_duplicate_aware_numeric_controls(
                Path("/missing-owner-private.ipa"))


if __name__ == "__main__":
    unittest.main()
