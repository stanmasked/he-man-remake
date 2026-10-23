"""Stage190: confirmed partial Symbol rotation/translation contract.

The six serialized float fields remain opaque. This helper models only the
integer rotation (degrees), X offset and Y offset confirmed in native code.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SymbolRotationTranslation:
    rotation_degrees: int
    offset_x: int
    offset_y: int

    def __post_init__(self) -> None:
        if type(self.rotation_degrees) is not int:
            raise ValueError("Rotation must be an integer number of degrees")
        if type(self.offset_x) is not int or type(self.offset_y) is not int:
            raise ValueError("Symbol offsets must be integers")

    @property
    def rotation_radians(self) -> float:
        return self.rotation_degrees * (math.pi / 180.0)

    def apply(self, x: float, y: float) -> tuple[float, float]:
        """Rotate a local point around the origin, then apply the confirmed offsets."""
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Local point coordinates must be finite")
        angle = self.rotation_radians
        cosine = math.cos(angle)
        sine = math.sin(angle)
        result_x = cosine * x - sine * y + self.offset_x
        result_y = sine * x + cosine * y + self.offset_y
        if not math.isfinite(result_x) or not math.isfinite(result_y):
            raise ValueError("Transformed point coordinates must be finite")
        return result_x, result_y
