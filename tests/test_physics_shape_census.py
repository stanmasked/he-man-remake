"""Stage140 fabricated-only ZIP references; no real iOS binary payloads."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import stat
import struct
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.physics_shape_census import (
    summarize_shape_lexemes, audit_private_physics_shape_census,
    _stem_pattern,
)
from test_shapes import circle, polygon


def utf16token(name: str) -> bytes:
    return struct.pack("<H", len(name)) + name.encode("utf-16le")


def fabricate(ipa: Path, *, unequal_struct=False, extra=(), corrupted_shape=False):
    entries = []
    for pack in ("screen-med", "screen-xlarge"):
        root=f"Payload/MOTU.app/{pack}/"
        entries.extend([
            (root+"geometry/FakeAlpha.shape",polygon()),
            (root+"geometry/FakeBeta.shape",
             b"not-a-shape" if corrupted_shape else circle()),
            (root+"geometry/FakeUnused.shape",circle()),
            # Actual source folders contain unrelated suffixes as well.
            (root+"geometry/Unrelated.geometry",b"UNRELATED"),
            (root+"physics_struct/FakeActor.ps2d",
             b"\0"*3 + utf16token("FakeAlpha") + b"\0\0" +
             utf16token("FakeBeta") + b"junk"),
            (root+"physics_struct/FakeStation.pstruct2d",
             b"fixture" + utf16token("FakeBeta") +
             (b"changed" if unequal_struct and pack=="screen-xlarge" else b"")),
            (root+"meta/GeometryData.repo",
             b"synthetic registry" + utf16token("FakeAlpha") + utf16token("FakeBeta")),
        ])
    entries.extend(extra)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(ipa,"w") as z:
            for name,raw in entries:
                if isinstance(name,ZipInfo):
                    z.writestr(name,raw)
                else:
                    z.writestr(name,raw)


class Stage140PhysicsShapeCensusTests(unittest.TestCase):
    def test_synthetic_private_packs_aggregate_candidate_edges(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"fake.ipa";fabricate(p)
            result=audit_private_physics_shape_census(p)
        self.assertEqual(result["paired_original_shape_count"],3)
        self.assertEqual(result["paired_physics_struct_resource_count"],2)
        self.assertEqual(result["physics_files_with_shape_identifier_lexeme"],2)
        self.assertEqual(result["physics_file_shape_identifier_candidate_pairs"],3)
        self.assertEqual(result["unique_shapes_lexically_referenced_in_physics_files"],2)
        self.assertEqual(result["shapes_with_matching_geometry_registry_lexeme"],2)
        self.assertEqual(result["physics_shape_lexemes_missing_in_geometry_registry"],0)
        self.assertFalse(result["original_physics_resource_binding_verified"])
        self.assertFalse(result["safe_for_switch_collision_import"])
        for secret in ("FakeAlpha","FakeBeta","FakeStation","FakeActor","FakeUnused",
                       "geometry/","physics_struct/","MOTU.app","synthetic registry"):
            self.assertNotIn(secret,json.dumps(result))

    def test_same_text_without_u16_prefix_does_not_count(self):
        result=summarize_shape_lexemes(
            {"Test.shape":circle()},
            {"Fixture.ps2d": "Test".encode("utf-16le")},
            utf16token("Test"))
        self.assertEqual(result["physics_files_with_shape_identifier_lexeme"],0)
        self.assertEqual(result["unique_shapes_lexically_referenced_in_physics_files"],0)

    def test_length_prefix_mismatch_does_not_count(self):
        result=summarize_shape_lexemes(
            {"Test.shape":circle()},
            {"Fixture.ps2d":struct.pack("<H",5)+"Test".encode("utf-16le")},
            utf16token("Test"))
        self.assertEqual(result["physics_file_shape_identifier_candidate_pairs"],0)

    def test_one_shape_in_two_physics_files_counts_two_edges_one_shape(self):
        shape={"Example.shape":polygon()}
        phys={"One.ps2d":utf16token("Example"),
              "Two.pstruct2d":utf16token("Example")}
        rep=summarize_shape_lexemes(shape,phys,utf16token("Example"))
        self.assertEqual(rep["physics_file_shape_identifier_candidate_pairs"],2)
        self.assertEqual(rep["unique_shapes_lexically_referenced_in_physics_files"],1)

    def test_registry_absence_is_observed_not_interpreted_as_owner(self):
        report=summarize_shape_lexemes(
            {"Linked.shape":circle()},
            {"Actor.ps2d":utf16token("Linked")},
            b"fictional unlinked registry")
        self.assertEqual(report["physics_shape_lexemes_missing_in_geometry_registry"],1)
        self.assertFalse(report["collision_hitbox_semantics_verified"])

    def test_duplicate_shape_stem_or_filename_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Invalid shape identifier"):
            summarize_shape_lexemes(
                {"folder/Bad.shape":circle()},
                {"Test.ps2d":b"123"},b"registry")

    def test_corrupt_shape_bytes_cannot_supply_census(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"synthetic.ipa";fabricate(p,corrupted_shape=True)
            with self.assertRaises(ValueError):
                audit_private_physics_shape_census(p)

    def test_unequal_original_screen_structs_are_rejected(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"synthetic.ipa";fabricate(p,unequal_struct=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_physics_shape_census(p)

    def test_missing_xlarge_physics_file_is_rejected(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"synthetic.ipa";fabricate(p)
            with ZipFile(p) as z:
                entries=[(i.filename,z.read(i)) for i in z.infolist()
                         if not i.filename.endswith("screen-xlarge/physics_struct/FakeActor.ps2d")]
            with ZipFile(p,"w") as z:
                for name,raw in entries:z.writestr(name,raw)
            with self.assertRaisesRegex(ValueError,"different resources"):
                audit_private_physics_shape_census(p)

    def test_duplicate_member_is_rejected(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"synthetic.ipa"
            fabricate(p,extra=[("Payload/MOTU.app/screen-med/geometry/FakeAlpha.shape",circle())])
            with self.assertRaisesRegex(ValueError,"Duplicate private ZIP"):
                audit_private_physics_shape_census(p)

    def test_selected_zip_symlink_is_rejected(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"synthetic.ipa"
            bad=[]
            # Both packs have the same selected path, so the structural
            # parity check passes and the symlink guard itself is tested.
            for pack in ("screen-med","screen-xlarge"):
                info=ZipInfo(f"Payload/MOTU.app/{pack}/physics_struct/Link.ps2d")
                info.create_system=3
                info.external_attr=(stat.S_IFLNK|0o777)<<16
                bad.append((info,b"relative.link"))
            fabricate(p,extra=bad)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_physics_shape_census(p)

    def test_selected_nested_shape_path_is_rejected(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"synthetic.ipa"
            fabricate(p,extra=[(
                "Payload/MOTU.app/screen-med/geometry/nested/Illegal.shape",circle())])
            with self.assertRaisesRegex(ValueError,"Malformed or nested"):
                audit_private_physics_shape_census(p)

    def test_size_budget_rejected_before_decompression(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"synthetic.ipa";fabricate(p)
            with patch("heman_tools.physics_shape_census.MAX_ITEM_BYTES",8):
                with self.assertRaisesRegex(ValueError,"unsafe selected"):
                    audit_private_physics_shape_census(p)

    def test_missing_private_archive_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner private IPA not found"):
            audit_private_physics_shape_census(Path("/missing/owner-copy.ipa"))


if __name__=="__main__":
    unittest.main()
