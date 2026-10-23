"""Stage193: fail-closed triage of residual SpriteCut UV exceptions.

Only aggregate counts leave the owner-private audit. Rendering/wrapping modes
are not inferred from the numeric cuts alone.
"""
from __future__ import annotations
from collections import Counter
from .sprite_cut_runtime_texture_bounds import classify_allocated_cut
from .sprite_cut_png_bounds_census import SpriteCutBoundsError


def triage_residuals(medium: dict, xlarge: dict) -> dict:
    if (not isinstance(medium, dict) or not isinstance(xlarge, dict)
            or not medium or set(medium) != set(xlarge)):
        raise SpriteCutBoundsError("Paired cut inventories must match")
    per_pack = {}
    classifications = {}
    for screen, inventory in (("screen-med", medium), ("screen-xlarge", xlarge)):
        statuses = {}
        counts = Counter()
        for key, entry in inventory.items():
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise SpriteCutBoundsError("Cut inventory entry is malformed")
            rect, dims = entry
            status, overflow_x, overflow_y = classify_allocated_cut(rect, dims)
            statuses[key] = status
            if status == "outside_allocated":
                axis = ("both" if overflow_x and overflow_y
                        else "horizontal" if overflow_x else "vertical")
                counts["outside_" + axis] += 1
                counts["max_horizontal"] = max(counts["max_horizontal"], overflow_x)
                counts["max_vertical"] = max(counts["max_vertical"], overflow_y)
            elif status == "invalid":
                counts["invalid"] += 1
            else:
                counts["safe_extent"] += 1
        classifications[screen] = statuses
        per_pack[screen] = {
            "safe_extent": counts["safe_extent"],
            "outside_horizontal_only": counts["outside_horizontal"],
            "outside_vertical_only": counts["outside_vertical"],
            "outside_both_axes": counts["outside_both"],
            "invalid": counts["invalid"],
            "max_horizontal_excess_pixels": counts["max_horizontal"],
            "max_vertical_excess_pixels": counts["max_vertical"],
        }
    paired = Counter((classifications["screen-med"][key],
                      classifications["screen-xlarge"][key]) for key in medium)
    return {
        "classification": "private_residual_uv_exception_triage",
        "per_pack": per_pack,
        "paired_status_counts": {
            f"{a}_med__{b}_xlarge": count
            for (a, b), count in sorted(paired.items())
        },
        "texture_wrap_or_clamp_mode_verified": False,
        "source_pixels_padded_or_synthesized": False,
        "unresolved_cuts_renderable": False,
        "resource_keys_offsets_or_per_record_data_exported": False,
    }
