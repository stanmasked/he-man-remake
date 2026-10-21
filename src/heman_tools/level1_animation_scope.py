"""Private iOS animation resource *scope* and first-level lexical evidence.

Stage151 established six first-level objects whose class names exactly
match two physics resources. This code tests those full, length-prefixed
UTF-16 identifiers across animation repositories, sprite WADs and
skeletal resources. A generic level state such as "idle" is not an
actor-specific animation binding.

Registries and skeletons must match between source screen packs. The
two sprite WADs are EXPECTED to differ; treat this as a resource-pack
hazard, NOT evidence of differing game behavior.

No decoded original animation, sprite bytes, object class strings,
per-object state labels or asset names enter the aggregate-only report.
Public tests use fictional resources only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .level_physics_shape_chains import FIRST_LEVEL
from .objects import parse_level_objects
from .physics_records import parse_physics_structure
from .physics_shape_census import (
    PREFIX, SCREENS, MAX_MEMBERS, MAX_PHYSICS,
    PHYSICS_DIR, _paired, _safe_read,
)

REPOSITORIES = (
    "meta/SpriteSeqData.repo",
    "meta/SpriteCutData.repo",
    "meta/SingleFrameSpriteData.repo",
)
WADS = ("sprite/SpriteSeqData.wad", "sprite/SpriteResData.wad")
SKELETON_DIR = "skeleton2D/"
SKELETON_EXTENSION = ".skel2d"
MAX_REPOSITORY_BYTES = 2_000_000
MAX_WAD_BYTES = 6_000_000
MAX_SKELETON_BYTES = 2_000_000
MAX_SKELETON_COUNT = 256
MAX_SKELETON_TOTAL = 8_000_000
MAX_LEVEL_BYTES = 8_000_000


def _utf16_full_token(name: str) -> bytes:
    if not isinstance(name, str) or not name:
        raise ValueError("Invalid source metadata identifier")
    encoded = name.encode("utf-16le", "strict")
    units = len(encoded)//2
    if not 1 <= units <= 512:
        raise ValueError("Source metadata identifier exceeds safety limit")
    return struct.pack("<H", units) + encoded


def _match_identifiers(names: set[str], resources: dict[str, bytes]
                       ) -> tuple[int, int]:
    """Number of DISTINCT source labels present in any resource.

    Count raw UTF16 full substrings and strict u16-length-prefixed UTF16
    separately. Neither is an established asset-table parser or link.
    """
    raw = prefixed = 0
    for name in names:
        full = name.encode("utf-16le", "strict")
        token = _utf16_full_token(name)
        raw += any(full in value for value in resources.values())
        prefixed += any(token in value for value in resources.values())
    return raw, prefixed


def summarize_animation_scopes(
    level: bytes,
    physics: dict[str, bytes],
    repositories: dict[str, dict[str, bytes]],
    wads: dict[str, dict[str, bytes]],
    skeletons: dict[str, dict[str, bytes]],
) -> dict:
    """Validate source pairing and return coarse counts only."""
    if type(level) is not bytes or not 1 <= len(level) <= MAX_LEVEL_BYTES:
        raise ValueError("Unsafe original first-level bytes")
    parsed = parse_level_objects(level)
    if parsed.level_name != FIRST_LEVEL:
        raise ValueError("Unexpected source first-level identity")
    if not isinstance(physics, dict) or not 1 <= len(physics) <= MAX_PHYSICS:
        raise ValueError("Missing original paired physics resources")

    physics_stems = set()
    for name, data in physics.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d"))
                or "/" in name or "\\" in name or
                type(data) is not bytes):
            raise ValueError("Invalid original physics resource")
        stem = name.rsplit(".",1)[0]
        if not stem or stem in physics_stems:
            raise ValueError("Ambiguous original physics resource stem")
        parse_physics_structure(data)
        physics_stems.add(stem)

    matches = [obj for obj in parsed.objects
               if obj.class_name in physics_stems]
    classes = {obj.class_name for obj in matches}
    states = {obj.state for obj in matches if obj.state}

    for dataset, required in ((repositories,set(REPOSITORIES)),
                              (wads,set(WADS))):
        if not isinstance(dataset,dict) or set(dataset) != set(SCREENS):
            raise ValueError("Missing original resolution-specific resources")
        if any(not isinstance(dataset[screen],dict)
               or set(dataset[screen]) != required for screen in SCREENS):
            raise ValueError("Missing original named resource bundle")
        for screen in SCREENS:
            if any(type(value) is not bytes or not value
                   for value in dataset[screen].values()):
                raise ValueError("Missing original resource bytes")

    if (not isinstance(skeletons,dict) or set(skeletons) != set(SCREENS)
            or any(not isinstance(skeletons[screen],dict) or
                   not 1 <= len(skeletons[screen]) <= MAX_SKELETON_COUNT
                   for screen in SCREENS)):
        raise ValueError("Missing or oversized original skeleton resources")
    skeleton_names = set(skeletons[SCREENS[0]])
    if set(skeletons[SCREENS[1]]) != skeleton_names:
        raise ValueError("Resolution-specific skeleton members differ")
    if any(not isinstance(name,str) or "/" in name or "\\" in name
           or not name.endswith(SKELETON_EXTENSION)
           for name in skeleton_names):
        raise ValueError("Invalid original skeleton filename")
    if any(type(blob) is not bytes or not 1 <= len(blob) <= MAX_SKELETON_BYTES
           for screen in SCREENS for blob in skeletons[screen].values()):
        raise ValueError("Unsafe original skeleton bytes")

    if any(repositories[SCREENS[0]][name] != repositories[SCREENS[1]][name]
           for name in REPOSITORIES):
        raise ValueError("Original animation registry differs between screen packs")
    if any(skeletons[SCREENS[0]][name] != skeletons[SCREENS[1]][name]
           for name in skeleton_names):
        raise ValueError("Original skeleton bytes differ between screen packs")

    differences = {
        name: sum(a != b for a,b in zip(
            wads[SCREENS[0]][name],wads[SCREENS[1]][name]
        )) + abs(len(wads[SCREENS[0]][name])-len(wads[SCREENS[1]][name]))
        for name in WADS
    }
    def matches_by_group(dataset: dict[str,dict[str,bytes]], labels:set[str]):
        # Aggregate across both packs; don't export any source identifier
        return {
            screen: _match_identifiers(labels,dataset[screen])
            for screen in SCREENS
        }
    result = {}
    for kind,resources in (("registries",repositories),
                           ("sprite_wads",wads),
                           ("skeletons",skeletons)):
        for label,identifiers in (("class",classes),("state",states)):
            matches_in_pack=matches_by_group(resources,identifiers)
            result[kind+"_"+label+"_raw_utf16_matching_distinct_names"] = max(
                value[0] for value in matches_in_pack.values()
            )
            result[kind+"_"+label+"_length_prefixed_utf16_matching_distinct_names"] = max(
                value[1] for value in matches_in_pack.values()
            )
            result[kind+"_"+label+"_matches_equal_across_screen_packs"] = (
                len(set(matches_in_pack.values())) == 1
            )

    return {
        "classification": "owner_private_level1_animation_resource_scope_and_lexical_census",
        "original_level1_object_instances":len(parsed.objects),
        "objects_with_exact_class_physics_name_match":len(matches),
        "distinct_linked_physics_class_names":len(classes),
        "distinct_state_labels_on_name_linked_level_objects":len(states),
        "paired_animation_registry_files":len(REPOSITORIES),
        "byte_identical_registry_file_pairs":len(REPOSITORIES),
        "paired_skeleton_resource_files":len(skeleton_names),
        "byte_identical_skeleton_file_pairs":len(skeleton_names),
        "paired_sprite_wad_files":len(WADS),
        "sprite_wad_file_pairs_with_different_contents":sum(
            value>0 for value in differences.values()
        ),
        "sprite_sequence_wad_differing_bytes":differences[WADS[0]],
        "sprite_resource_wad_differing_bytes":differences[WADS[1]],
        **result,
        "animation_repository_entries_structurally_decoded":False,
        "sprite_wad_structures_decoded":False,
        "first_level_physics_class_to_animation_state_binding_verified":False,
        "same_named_state_proves_actor_specific_animation":False,
        "source_iOS_animation_playback_verified":False,
        "switch_original_animation_import_permitted":False,
        "original_sprite_data_classes_states_paths_pixels_or_hashes_in_output":False,
    }


def audit_private_animation_scopes(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA does not exist")
    with ZipFile(ipa) as archive:
        members=archive.infolist()
        if len(members)>MAX_MEMBERS:
            raise ValueError("Original IPA ZIP index exceeds safety budget")
        index={m.filename:m for m in members}
        if len(index)!=len(members):
            raise ValueError("Duplicate original IPA ZIP member")
        def get(screen,subpath,max_size):
            return _safe_read(archive,index.get(PREFIX+screen+"/"+subpath),
                              max_size)
        level=get(SCREENS[0],"levels/"+FIRST_LEVEL,MAX_LEVEL_BYTES)
        # Two original level resolution packs must be byte identical.
        if level!=get(SCREENS[1],"levels/"+FIRST_LEVEL,MAX_LEVEL_BYTES):
            raise ValueError("Original first-level bytes differ across screens")
        physics=_paired(archive,index,PHYSICS_DIR,
                        (".ps2d",".pstruct2d"),max_items=MAX_PHYSICS)
        repos={screen:{name:get(screen,name,MAX_REPOSITORY_BYTES)
                       for name in REPOSITORIES} for screen in SCREENS}
        wads={screen:{name:get(screen,name,MAX_WAD_BYTES)
                      for name in WADS} for screen in SCREENS}
        skeletons={}
        for screen in SCREENS:
            prefix=PREFIX+screen+"/"+SKELETON_DIR
            files={}
            for original_name in index:
                if original_name.startswith(prefix) and original_name.endswith(
                        SKELETON_EXTENSION):
                    tail=original_name[len(prefix):]
                    if not tail or "/" in tail or "\\" in tail or len(tail)>255:
                        raise ValueError("Unsupported source skeleton nesting")
                    files[tail]=get(screen,SKELETON_DIR+tail,
                                    MAX_SKELETON_BYTES)
            if not 1<=len(files)<=MAX_SKELETON_COUNT or (
                sum(map(len,files.values()))>MAX_SKELETON_TOTAL
            ):
                raise ValueError("Missing or excessively large source skeleton group")
            skeletons[screen]=files
        return summarize_animation_scopes(level,physics,repos,wads,skeletons)


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    opts=ap.parse_args(argv)
    destination=private_output_path(opts.out)
    report=audit_private_animation_scopes(opts.ipa)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",
                           encoding="utf-8")
    print("First-level animation resource scope census saved privately (aggregate only).")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
