"""Stage186: asset-free reference model for the native directional-sprite selector.

Private ARMv7 method inspection established a four-slot resource selector.
This model intentionally uses synthetic resource keys only; it is not a
renderer and does not infer the actor-state-to-message mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# The native selector's switch order is 0, 1, 3, 2 in serialized slot order.
_SELECTOR_TO_SLOT = (0, 1, 3, 2)


@dataclass(frozen=True)
class DirectionalSelectionDecision:
    selector: int
    slot_index: int | None
    resource_key: str | None
    clears_current_sequence: bool
    starts_playback: bool
    reset_to_first_frame: bool


def decide_directional_selection(
    sequence_slots: Sequence[str | None],
    selector: int,
    *,
    reset_to_first_frame: bool,
) -> DirectionalSelectionDecision:
    """Model CDirectionalSprite's observed selection contract.

    `sequence_slots` is the four preloaded resource slots in storage order.
    Selector values outside 0..3 clear the active sequence; a missing chosen
    slot also clears it. There is deliberately no fallback to another slot.
    """
    if not isinstance(sequence_slots, (tuple, list)) or len(sequence_slots) != 4:
        raise ValueError("Exactly four directional sequence slots are required")
    for key in sequence_slots:
        if key is not None and (not isinstance(key, str) or not key):
            raise ValueError("Sequence slots must contain non-empty keys or None")
    if type(selector) is not int:
        raise ValueError("Directional selector must be an integer")
    if type(reset_to_first_frame) is not bool:
        raise ValueError("Reset flag must be boolean")

    if selector < 0 or selector >= len(_SELECTOR_TO_SLOT):
        return DirectionalSelectionDecision(
            selector=selector,
            slot_index=None,
            resource_key=None,
            clears_current_sequence=True,
            starts_playback=False,
            reset_to_first_frame=reset_to_first_frame,
        )

    slot_index = _SELECTOR_TO_SLOT[selector]
    key = sequence_slots[slot_index]
    if key is None:
        return DirectionalSelectionDecision(
            selector=selector,
            slot_index=slot_index,
            resource_key=None,
            clears_current_sequence=True,
            starts_playback=False,
            reset_to_first_frame=reset_to_first_frame,
        )

    return DirectionalSelectionDecision(
        selector=selector,
        slot_index=slot_index,
        resource_key=key,
        clears_current_sequence=False,
        starts_playback=True,
        reset_to_first_frame=reset_to_first_frame,
    )
