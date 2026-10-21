"""Stage152 wholly artificial animation resource scope and ZIP security tests."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.level1_animation_scope import (
    REPOSITORIES, WADS, SCREENS, _utf16_full_token,
    summarize_animation_scopes, audit_private_animation_scopes,
)
from heman_tools.level_physics_shape_chains import FIRST_LEVEL
from test_objects import example_level
from test_level_map_links import map_object
from test_physics_records import fixture,record


def samples(*, embed_class=False, embed_state=True, wad_diff=True):
    level=example_level([
        map_object("FakeActor", name="alpha"),
        map_object("FakeActor", name="beta"),
        map_object("UnrelatedActor",name="gamma"),
    ],name=FIRST_LEVEL)
    physics={"FakeActor.ps2d":fixture([record(names=("FakeGeometry",))]),
             "Unused.pstruct2d":fixture([record(names=("Other",))])}
    class_string=_utf16_full_token("FakeActor")
    state_string=_utf16_full_token("idle")
    reg_data=b"fictional-registry-data"+(class_string if embed_class else b"")+(
        state_string if embed_state else b"")
    repos={screen:{name:reg_data for name in REPOSITORIES} for screen in SCREENS}
    wads={screen:{
        WADS[0]:(b"fake-sprite-sequence"+(class_string if embed_class else b"")+
                 state_string+(b"A" if screen==SCREENS[0] else b"B")
                 if wad_diff else b"same-sequences"),
        WADS[1]:(b"fake-sprite-resource"+(b"X" if screen==SCREENS[0]
                                          else b"Y") if wad_diff
                 else b"same-resources")
    } for screen in SCREENS}
    skeletons={screen:{"FabricatedRig.skel2d":b"fictitious-skeleton-payload"}
               for screen in SCREENS}
    return level, physics, repos, wads, skeletons


def synthetic_ipa(path, *, wad_diff=True, bad_peer_registry=False,
                  bad_skeleton=False, extra=()):
    level,physics,repos,wads,skeletons=samples(wad_diff=wad_diff)
    if bad_peer_registry:
        repos[SCREENS[1]][REPOSITORIES[0]]=b"CHANGED"
    if bad_skeleton:
        skeletons[SCREENS[1]]["FabricatedRig.skel2d"]=b"DIFFERENT"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as z:
            for screen in SCREENS:
                prefix=f"Payload/MOTU.app/{screen}/"
                z.writestr(prefix+"levels/"+FIRST_LEVEL,level)
                for name,blob in physics.items():
                    z.writestr(prefix+"physics_struct/"+name,blob)
                for name,blob in repos[screen].items():
                    z.writestr(prefix+name,blob)
                for name,blob in wads[screen].items():
                    z.writestr(prefix+name,blob)
                for name,blob in skeletons[screen].items():
                    z.writestr(prefix+"skeleton2D/"+name,blob)
            for name,blob in extra:
                z.writestr(name,blob)


class Stage152AnimationResourceScopesTests(unittest.TestCase):
    def check(self,params=None):
        return summarize_animation_scopes(*(params or samples()))

    def test_byte_identical_registries_and_skeletons(self):
        result=self.check()
        self.assertEqual(result["paired_animation_registry_files"],3)
        self.assertEqual(result["byte_identical_registry_file_pairs"],3)
        self.assertEqual(result["paired_skeleton_resource_files"],1)
        self.assertEqual(result["byte_identical_skeleton_file_pairs"],1)

    def test_res_specific_wads_differ_without_false_rejection(self):
        result=self.check()
        self.assertEqual(result["paired_sprite_wad_files"],2)
        self.assertEqual(result["sprite_wad_file_pairs_with_different_contents"],2)
        self.assertEqual(result["sprite_sequence_wad_differing_bytes"],1)
        self.assertEqual(result["sprite_resource_wad_differing_bytes"],1)

    def test_identical_wads_are_allowed_as_synthetic_control(self):
        result=self.check(samples(wad_diff=False))
        self.assertEqual(result["sprite_wad_file_pairs_with_different_contents"],0)
        self.assertEqual(result["sprite_sequence_wad_differing_bytes"],0)
        self.assertEqual(result["sprite_resource_wad_differing_bytes"],0)

    def test_class_identifiers_are_not_assumed_to_appear_in_sprites(self):
        result=self.check()
        self.assertEqual(result["original_level1_object_instances"],3)
        self.assertEqual(result["objects_with_exact_class_physics_name_match"],2)
        self.assertEqual(result["distinct_linked_physics_class_names"],1)
        for group in ("registries","sprite_wads","skeletons"):
            self.assertEqual(result[group+"_class_raw_utf16_matching_distinct_names"],0)
            self.assertEqual(result[group+"_class_length_prefixed_utf16_matching_distinct_names"],0)
        self.assertFalse(result["first_level_physics_class_to_animation_state_binding_verified"])

    def test_explicit_fake_class_name_can_match_utf16_evidence(self):
        result=self.check(samples(embed_class=True))
        self.assertEqual(result["registries_class_raw_utf16_matching_distinct_names"],1)
        self.assertEqual(result["registries_class_length_prefixed_utf16_matching_distinct_names"],1)
        self.assertEqual(result["sprite_wads_class_length_prefixed_utf16_matching_distinct_names"],1)
        self.assertFalse(result["source_iOS_animation_playback_verified"])

    def test_shared_idle_label_does_not_identify_actor_specific_animation(self):
        result=self.check()
        self.assertEqual(result["distinct_state_labels_on_name_linked_level_objects"],1)
        self.assertEqual(result["registries_state_raw_utf16_matching_distinct_names"],1)
        self.assertEqual(result["sprite_wads_state_length_prefixed_utf16_matching_distinct_names"],1)
        self.assertFalse(result["same_named_state_proves_actor_specific_animation"])

    def test_state_label_absent_from_both_packs_has_zero_signal(self):
        result=self.check(samples(embed_state=False,wad_diff=False))
        self.assertEqual(result["registries_state_length_prefixed_utf16_matching_distinct_names"],0)

    def test_state_name_does_not_count_as_linked_class(self):
        result=self.check()
        self.assertEqual(result["registries_state_raw_utf16_matching_distinct_names"],1)
        self.assertEqual(result["registries_class_raw_utf16_matching_distinct_names"],0)

    def test_fake_skeleton_token_can_be_a_candidate_but_not_binding(self):
        level,phys,regs,wads,rigs=samples()
        for screen in SCREENS:
            rigs[screen]["FabricatedRig.skel2d"]+=_utf16_full_token("FakeActor")
        result=self.check((level,phys,regs,wads,rigs))
        self.assertEqual(result["skeletons_class_length_prefixed_utf16_matching_distinct_names"],1)
        self.assertFalse(result["first_level_physics_class_to_animation_state_binding_verified"])

    def test_unsynchronized_registry_bytes_are_rejected(self):
        level,phys,regs,wads,rigs=samples()
        regs[SCREENS[1]][REPOSITORIES[0]]=b"NotEqual"
        with self.assertRaisesRegex(ValueError,"registry differs"):
            self.check((level,phys,regs,wads,rigs))

    def test_unsynchronized_skeleton_bytes_are_rejected(self):
        level,phys,regs,wads,rigs=samples()
        rigs[SCREENS[1]]["FabricatedRig.skel2d"]=b"NotEqual"
        with self.assertRaisesRegex(ValueError,"skeleton bytes differ"):
            self.check((level,phys,regs,wads,rigs))

    def test_different_skeleton_member_set_fails_closed(self):
        level,phys,regs,wads,rigs=samples()
        rigs[SCREENS[1]]["Additional.skel2d"]=b"fake"
        with self.assertRaisesRegex(ValueError,"members differ"):
            self.check((level,phys,regs,wads,rigs))

    def test_missing_registry_fails_closed(self):
        level,phys,regs,wads,rigs=samples()
        del regs[SCREENS[1]][REPOSITORIES[2]]
        with self.assertRaisesRegex(ValueError,"Missing original named resource"):
            self.check((level,phys,regs,wads,rigs))

    def test_bad_physics_resource_cannot_become_animation_evidence(self):
        level,phys,regs,wads,rigs=samples()
        phys["FakeActor.ps2d"]=b"invalid"
        with self.assertRaises(ValueError):
            self.check((level,phys,regs,wads,rigs))

    def test_fuzzy_class_prefix_is_not_full_exact_match(self):
        level,phys,regs,wads,rigs=samples()
        del phys["FakeActor.ps2d"]
        phys["FakeActorExtended.ps2d"]=fixture([record()])
        report=self.check((level,phys,regs,wads,rigs))
        self.assertEqual(report["objects_with_exact_class_physics_name_match"],0)
        self.assertEqual(report["distinct_linked_physics_class_names"],0)

    def test_duplicate_physics_stem_disallowed(self):
        level,phys,regs,wads,rigs=samples()
        phys["FakeActor.pstruct2d"]=phys["FakeActor.ps2d"]
        with self.assertRaisesRegex(ValueError,"Ambiguous"):
            self.check((level,phys,regs,wads,rigs))

    def test_no_private_names_or_resource_bytes_in_summary(self):
        rendered=json.dumps(self.check())
        for secret in ("FakeActor","FabricatedRig","Fictional",
                       "fake-sprite-sequence","physics_struct/",
                       "skeleton2D/","idle","alpha"):
            self.assertNotIn(secret,rendered)
        self.assertFalse(json.loads(rendered)[
            "original_sprite_data_classes_states_paths_pixels_or_hashes_in_output"])

    def test_synthetic_archive_integrates_without_original_game_assets(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"synthetic.ipa"
            synthetic_ipa(path)
            result=audit_private_animation_scopes(path)
        self.assertEqual(result["objects_with_exact_class_physics_name_match"],2)
        self.assertEqual(result["sprite_wad_file_pairs_with_different_contents"],2)

    def test_paired_original_repo_difference_fails_in_archive(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"synthetic.ipa"
            synthetic_ipa(path,bad_peer_registry=True)
            with self.assertRaisesRegex(ValueError,"registry differs"):
                audit_private_animation_scopes(path)

    def test_paired_original_rig_difference_fails_in_archive(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"synthetic.ipa"
            synthetic_ipa(path,bad_skeleton=True)
            with self.assertRaisesRegex(ValueError,"skeleton bytes differ"):
                audit_private_animation_scopes(path)

    def test_duplicate_archive_entry_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"synthetic.ipa"
            synthetic_ipa(path,extra=[(
                "Payload/MOTU.app/screen-med/meta/SpriteSeqData.repo",b"fake")])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_animation_scopes(path)

    def test_paired_skeleton_symlink_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"synthetic.ipa"
            extras=[]
            for screen in SCREENS:
                symlink=ZipInfo(
                    f"Payload/MOTU.app/{screen}/skeleton2D/Link.skel2d")
                symlink.create_system=3
                symlink.external_attr=(stat.S_IFLNK|0o777)<<16
                extras.append((symlink,b"target"))
            synthetic_ipa(path,extra=extras)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_animation_scopes(path)

    def test_oversized_wad_member_rejected_before_extraction(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"synthetic.ipa"
            synthetic_ipa(path)
            from unittest.mock import patch
            with patch("heman_tools.level1_animation_scope.MAX_WAD_BYTES",4):
                with self.assertRaisesRegex(ValueError,"unsafe selected"):
                    audit_private_animation_scopes(path)

    def test_private_ipa_required(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA"):
            audit_private_animation_scopes(Path("/not-here/original.ipa"))


if __name__=="__main__":
    unittest.main()
