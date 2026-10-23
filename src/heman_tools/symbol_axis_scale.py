"""Stage190: confirmed per-axis Symbol scale multipliers."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SymbolAxisScale:
    """The final two Symbol floats scale local X and Y coordinates independently."""

    scale_x: float
    scale_y: float

    def __post_init__(self) -> None:
        if (isinstance(self.scale_x, bool) or isinstance(self.scale_y, bool)
                or not isinstance(self.scale_x, (int, float))
                or not isinstance(self.scale_y, (int, float))
                or not math.isfinite(self.scale_x) or not math.isfinite(self.scale_y)):
            raise ValueError("Axis scales must be finite numeric values")

    def apply(self, x: float, y: float) -> tuple[float, float]:
        """Scale a local point, offset, or dimension pair without clipping or mirroring loss."""
        if (isinstance(x, bool) or isinstance(y, bool)
                or not isinstance(x, (int, float)) or not isinstance(y, (int, float))
                or not math.isfinite(x) or not math.isfinite(y)):
            raise ValueError("Local coordinates must be finite numeric values")
        result = (float(x) * float(self.scale_x), float(y) * float(self.scale_y))
        if not math.isfinite(result[0]) or not math.isfinite(result[1]):
            raise ValueError("Scaled coordinates must remain finite")
        return result
