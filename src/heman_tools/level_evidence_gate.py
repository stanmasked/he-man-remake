"""Strict evidence gate for candidate level geometry; no original assets or maps.

Inputs are boolean verification assertions recorded manually after private
investigation. Passing numerical fits alone never authorizes collision export.
"""
from __future__ import annotations

REQUIRED = (
    "level_object_identity",
    "shape_ownership",
    "coordinate_scale",
    "axis_orientation",
    "cross_frame_validation",
    "heldout_validation",
    "collision_category",
    "original_gameplay_trace",
)


def assess_geometry_evidence(evidence: dict) -> dict:
    """Return a fail-closed research readiness report, never a geometry mask."""
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")
    if set(evidence) - set(REQUIRED):
        raise ValueError("unknown evidence field")
    if any(type(value) is not bool for value in evidence.values()):
        raise ValueError("evidence values must be explicit booleans")
    missing = [key for key in REQUIRED if evidence.get(key) is not True]
    return {
        "all_required_checks_recorded": not missing,
        "missing_evidence": missing,
        "candidate_ready_for_manual_review": not missing,
        "automatic_collision_export_permitted": False,
        "physical_switch_gameplay_verified": False,
        "explanation": (
            "Evidence declarations are not independently authenticated. "
            "Even a complete checklist requires manual source-private review "
            "before any game-world collision geometry is implemented."
        ),
    }
