"""Stage188: fail-closed alias -> east/west SpriteSequence resolver model.

This is an asset-free reference model for the next renderer integration layer.
It is deliberately separate from CDirectionalSprite's four-slot selector and
does not map gameplay-state handles to aliases.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence


Direction = Literal["east", "west"]
ResolutionStatus = Literal["resolved", "missing", "ambiguous"]


@dataclass(frozen=True)
class DirectionalSequenceEntry:
    alias: str
    variant: int
    east_key: str
    west_key: str


@dataclass(frozen=True)
class DirectionalSequenceResolution:
    status: ResolutionStatus
    resource_key: str | None


def _validate_entry(entry: DirectionalSequenceEntry) -> None:
    if not isinstance(entry, DirectionalSequenceEntry):
        raise ValueError("Every table entry must be a DirectionalSequenceEntry")
    if not isinstance(entry.alias, str) or not entry.alias:
        raise ValueError("Alias labels must be non-empty strings")
    if type(entry.variant) is not int or entry.variant < 0:
        raise ValueError("Variant must be a non-negative integer")
    if not isinstance(entry.east_key, str) or not entry.east_key:
        raise ValueError("East resource keys must be non-empty strings")
    if not isinstance(entry.west_key, str) or not entry.west_key:
        raise ValueError("West resource keys must be non-empty strings")


def resolve_directional_sequence(
    entries: Sequence[DirectionalSequenceEntry],
    alias: str,
    variant: int,
    direction: Direction,
    *,
    ambiguous_aliases: Sequence[tuple[int, str]] | set[tuple[int, str]] = (),
) -> DirectionalSequenceResolution:
    """Resolve one alias only within the requested variant; never guess a fallback."""
    if not isinstance(entries, (tuple, list)):
        raise ValueError("Entries must be a tuple or list")
    if not isinstance(alias, str) or not alias:
        raise ValueError("Alias must be a non-empty string")
    if type(variant) is not int or variant < 0:
        raise ValueError("Variant must be a non-negative integer")
    if direction not in ("east", "west"):
        raise ValueError("Direction must be 'east' or 'west'")
    for entry in entries:
        _validate_entry(entry)
    if not isinstance(ambiguous_aliases, (tuple, list, set, frozenset)):
        raise ValueError("Ambiguous alias collection is invalid")

    ambiguous = set()
    for item in ambiguous_aliases:
        if (not isinstance(item, tuple) or len(item) != 2
                or type(item[0]) is not int or item[0] < 0
                or not isinstance(item[1], str) or not item[1]):
            raise ValueError("Ambiguous alias entries must be (variant, non-empty alias) pairs")
        ambiguous.add(item)

    if (variant, alias) in ambiguous:
        return DirectionalSequenceResolution("ambiguous", None)

    matches = [entry for entry in entries
               if entry.variant == variant and entry.alias == alias]
    if len(matches) > 1:
        return DirectionalSequenceResolution("ambiguous", None)
    if not matches:
        return DirectionalSequenceResolution("missing", None)

    entry = matches[0]
    key = entry.east_key if direction == "east" else entry.west_key
    return DirectionalSequenceResolution("resolved", key)
