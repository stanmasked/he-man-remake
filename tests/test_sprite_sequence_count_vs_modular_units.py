"""Stage166: fabricated-only count/reference/modular-width falsification."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import struct
import unittest

from heman_tools.sprite_repo_wad_index import (
    SCREENS, SpriteIndexFormatError, parse_sprite_repository,
)
from heman_tools.sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from heman_tools.sprite_sequence_count_vs_modular_units import (
    _comparison, _extra_82_units,
    summarize_sequence_count_vs_modular_units,
    audit_private_sequence_count_vs_modular_units,
)
from test_sprite_repo_wad_index import repository, string
from test_sprite_sequence_nested_grammar import (
    make_fake_packs, invented_sequence, first_cut, CUT_KEYS, CUT_WAD,
)
from test_sprite_sequence_cut_decoy_controls import fabricated_zip


def invented_counterexample_packs():
    """Fictional records selected to disprove simplistic interpretations."""
    records = (
        ("Empty", 0, b""),
        ("LongOne", 1, first_cut() + b"\xf8" * 146),
        ("BaseOne", 1, first_cut() + b"\xf8" * 64),
        ("MoreThanTwo", 3, first_cut() + b"\xf8" * 64 +
         b"\xcc" * 12 + first_cut("CutB") + b"\xf8" * 64),
        ("TwoWithExtra", 2, first_cut() + b"\xf8" * 146 +
         b"\xcc" * 33 + first_cut("CutC") + b"\xf8" * 146),
    )
    repos, wads, cuts = {}, {}, {}
    for screen in SCREENS:
        offsets, pieces, offset = [], [], 0
        for name, count, body in records:
            piece = invented_sequence(name, count, body)
            offsets.append(offset)
            pieces.append(piece)
            offset += len(piece)
        repos[screen] = repository(
            "SpriteSeqData", WAD_PATH,
            tuple(name for name, _, _ in records), tuple(offsets),
        )
        wads[screen] = b"".join(pieces)
        cuts[screen] = repository(
            "SpriteCutData", CUT_WAD, CUT_KEYS, (0,30,60,90),
        )
    return repos, wads, cuts


class Stage166FakeCountVsWidthTests(unittest.TestCase):
    def report(self, source=None):
        return summarize_sequence_count_vs_modular_units(
            *(make_fake_packs() if source is None else source)
        )

    def row(self, source=None, count="two", word="first_u32_one"):
        return self.report(source)["by_firstword_and_declared_count"][
            word][count]

    def test_comparison_helper_all_three_relations(self):
        self.assertEqual(_comparison(0, 1), "less_than_unknown_count")
        self.assertEqual(_comparison(2, 2), "equal_unknown_count")
        self.assertEqual(_comparison(3, 2), "greater_than_unknown_count")

    def test_comparison_rejects_boolean_or_negative(self):
        for a, b in ((True,1),(0,0),(-1,3),("2",2)):
            with self.subTest(values=(a,b)), self.assertRaises(ValueError):
                _comparison(a,b)

    def test_exact_eighty_two_modular_extension_counts(self):
        self.assertEqual(_extra_82_units((), 64), 0)
        self.assertEqual(_extra_82_units((), 146), 1)
        self.assertEqual(_extra_82_units((), 228), 2)
        self.assertEqual(_extra_82_units((76,), 64), 0)
        self.assertEqual(_extra_82_units((158,), 64), 1)
        self.assertEqual(_extra_82_units((179,), 146), 2)
        self.assertEqual(_extra_82_units((76, 97, 118), 64), 0)

    def test_nonmatching_geometry_never_gets_silent_zero_units(self):
        for gaps, tail in (((77,),64), ((76,),65),
                           ((0,),64), ((),65)):
            with self.subTest(gaps=gaps,tail=tail):
                self.assertIsNone(_extra_82_units(gaps,tail))

    def test_invalid_modular_inputs_fail_closed(self):
        for gaps, tail in ((None,64), ([76],64), ((76,),True),
                           ((76,),-1)):
            with self.subTest(gaps=gaps,tail=tail):
                with self.assertRaises(ValueError):
                    _extra_82_units(gaps,tail)

    def test_default_fixture_name_reference_counts(self):
        r = self.row()
        x = r["registered_name_reference_count_vs_unknown_u32"]
        self.assertEqual(x["equal_unknown_count"], 2)
        self.assertEqual(x["greater_than_unknown_count"], 1)
        self.assertEqual(x["less_than_unknown_count"], 0)

    def test_default_fixture_extra82_block_count_not_automatically_frame_count(self):
        r = self.row()
        x = r["extra_82_byte_extensions_vs_unknown_u32"]
        self.assertEqual(x["less_than_unknown_count"], 1)
        self.assertEqual(x["equal_unknown_count"], 1)
        self.assertEqual(x["greater_than_unknown_count"], 0)
        self.assertEqual(r["unclassifiable_under_82_geometry"], 1)

    def test_firstword_one_single_candidate_name_counts(self):
        r = self.row(count="one")
        self.assertEqual(r["known_first_cut_records"], 2)
        self.assertEqual(r["complete_modular_geometry"], 1)
        self.assertEqual(r["unclassifiable_under_82_geometry"], 1)
        self.assertEqual(r[
            "registered_name_reference_count_vs_unknown_u32"
        ]["equal_unknown_count"], 2)

    def test_long_single_unknown_count_one_but_positive_82_extension(self):
        r = self.row(invented_counterexample_packs(),count="one")
        self.assertEqual(r["known_first_cut_records"], 2)
        self.assertEqual(r["unknown_count_one_with_positive_extra_82_units"], 1)
        self.assertEqual(r["complete_modular_geometry"], 2)

    def test_multi_unknown_count_three_but_no_82_extensions(self):
        r = self.row(invented_counterexample_packs(),count="three_four")
        self.assertEqual(r["unknown_count_multi_with_zero_extra_82_units"], 1)
        self.assertEqual(r["registered_name_reference_count_vs_unknown_u32"][
            "less_than_unknown_count"], 1)

    def test_counterexample_two_unknown_count_with_two_extensions(self):
        r = self.row(invented_counterexample_packs(), count="two")
        self.assertEqual(r["extra_82_byte_extensions_vs_unknown_u32"][
            "equal_unknown_count"], 1)

    def test_compound_source_record_totals_close(self):
        r = self.report(invented_counterexample_packs())
        totals = [v for g in r["by_firstword_and_declared_count"].values()
                  for v in g.values()]
        self.assertEqual(sum(v["known_first_cut_records"] for v in totals), 4)
        self.assertEqual(sum(v["complete_modular_geometry"] for v in totals), 4)
        self.assertEqual(sum(v["unclassifiable_under_82_geometry"] for v in totals),0)

    def test_screen_specific_opaque_changes_preserve_count_evidence(self):
        repos,wads,cuts = make_fake_packs()
        wads[SCREENS[1]] = wads[SCREENS[1]].replace(
            b"\xfe"*64,b"\xfa"*64)
        self.assertEqual(self.row((repos,wads,cuts)),self.row())

    def test_firstword_other_uses_independent_group(self):
        repos,wads,cuts = make_fake_packs()
        for screen in SCREENS:
            row = next(x for x in parse_sprite_repository(
                repos[screen],expected_label="SpriteSeqData",
                expected_wad=WAD_PATH) if x.key=="FakeDouble")
            raw=bytearray(wads[screen])
            struct.pack_into("<I",raw,row.offset+len(string(row.key))+8,2)
            wads[screen]=bytes(raw)
        r=self.row((repos,wads,cuts), word="first_u32_other")
        self.assertEqual(r["known_first_cut_records"],1)

    def test_invalid_paired_header_detected(self):
        repos,wads,cuts = make_fake_packs()
        b=bytearray(wads[SCREENS[1]])
        row=next(x for x in parse_sprite_repository(
            repos[SCREENS[1]], expected_label="SpriteSeqData",
            expected_wad=WAD_PATH) if x.key=="FakeDouble")
        struct.pack_into("<I",b,row.offset+len(string(row.key))+8,8)
        wads[SCREENS[1]]=bytes(b)
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos,wads,cuts))

    def test_export_has_no_raw_names_or_intervals(self):
        r=self.report(invented_counterexample_packs())
        s=json.dumps(r)
        for token in ("LongOne","MoreThanTwo","CutA","CutB",
                      "private_word_8","offset_99","per_record_gap_array"):
            self.assertNotIn(token,s)
        for key in ("all_name_references_are_proven_animation_frames",
                    "unknown_u32_is_proven_animation_frame_count",
                    "modular_82_extensions_are_proven_rendered_frames",
                    "frame_durations_transitions_hitboxes_or_runtime_verified",
                    "original_sprite_import_to_switch_permitted",
                    "original_names_header_values_offsets_and_gap_arrays_exported"):
            self.assertFalse(r[key])

    def test_synthetic_zip_integration(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"invented.ipa"
            fabricated_zip(path,invented_counterexample_packs())
            result=audit_private_sequence_count_vs_modular_units(path)
        self.assertTrue(result["independent_stage165_lexical_and_gap_controls_reconciled"])

    def test_duplicate_zip_member_rejected(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"invented.ipa"
            fabricated_zip(path,make_fake_packs(),extra=[(
                "Payload/MOTU.app/"+SCREENS[0]+"/"+REPO_PATH,b"duplicated")])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_sequence_count_vs_modular_units(path)

    def test_symlink_to_selected_wad_rejected(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"invented.ipa"
            fabricated_zip(path,make_fake_packs(),symlink=True)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_sequence_count_vs_modular_units(path)

    def test_missing_source_ipa_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA"):
            audit_private_sequence_count_vs_modular_units(
                Path("/does-not-exist/heman-private.ipa"))


if __name__=="__main__":
    unittest.main()
