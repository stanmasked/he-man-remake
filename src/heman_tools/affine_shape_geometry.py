"""Mathematical candidate envelopes for a shape under an affine 3x3 matrix.

These generic coordinate calculations do NOT establish original game units,
shape-to-object ownership, real hitboxes, or physical collision behavior.
"""
from __future__ import annotations

import math

from .shapes import Shape, affine_point


def _valid_affine(matrix: tuple[float, ...]) -> None:
    """Require the previously observed *column-major* 2D affine layout."""
    if (len(matrix) != 9 or not all(math.isfinite(v) for v in matrix)
            or abs(matrix[2]) > 1e-5
            or abs(matrix[5]) > 1e-5
            or abs(matrix[8] - 1) > 1e-5):
        raise ValueError("expected a finite 2D affine 3x3 matrix")


def affine_diagnostics(matrix: tuple[float, ...]) -> dict:
    """Describe matrix distortion in uncalibrated local/world units.

    Columns (a,b), (c,d) transform a local X/Y basis respectively. A
    zero determinant denotes collapsed area; negative means reflection.
    This classification is numerical geometry, not a gameplay contract.
    """
    _valid_affine(matrix)
    a, b, c, d = matrix[0], matrix[1], matrix[3], matrix[4]
    axis_x = math.hypot(a, b)
    axis_y = math.hypot(c, d)
    product = axis_x * axis_y
    determinant = a * d - b * c
    dot = a * c + b * d
    if not all(math.isfinite(v) for v in (axis_x, axis_y, product, determinant, dot)):
        raise ValueError("affine matrix calculations overflow")
    degenerate = product == 0 or abs(determinant) <= 1e-12 * product
    cosine = None if product == 0 else max(-1., min(1., dot / product))
    return {
        "determinant": determinant,
        "local_x_axis_length": axis_x,
        "local_y_axis_length": axis_y,
        "axis_cosine": cosine,
        "near_degenerate": degenerate,
        "reflected": determinant < 0 and not degenerate,
        "units_verified": False,
    }


def hypothetical_shape_aabb(shape: Shape,
                            matrix: tuple[float, ...]) -> tuple[float, float, float, float]:
    """Exact transformed *math* AABB for polygons and affine-mapped circles.

    A circle under nonuniform scale or shear becomes an ellipse. Each output
    axis extent is radius * Euclidean norm of the corresponding matrix row;
    transforming only the circle's bounding-box corners is NOT exact.
    """
    _valid_affine(matrix)
    if shape.kind == "polygon":
        if len(shape.vertices) < 3:
            raise ValueError("polygon requires at least three vertices")
        mapped = [affine_point(v, matrix) for v in shape.vertices]
        if not all(math.isfinite(n) for point in mapped for n in point):
            raise ValueError("transformed polygon coordinates overflow")
        xs, ys = zip(*mapped)
        bounds = (min(xs), min(ys), max(xs), max(ys))
    elif shape.kind == "circle":
        if (shape.center is None or shape.radius is None
                or not math.isfinite(shape.radius) or shape.radius <= 0):
            raise ValueError("invalid circle geometry")
        center_x, center_y = affine_point(shape.center, matrix)
        horizontal = shape.radius * math.hypot(matrix[0], matrix[3])
        vertical = shape.radius * math.hypot(matrix[1], matrix[4])
        bounds = (center_x - horizontal, center_y - vertical,
                  center_x + horizontal, center_y + vertical)
    else:
        raise ValueError("unsupported shape kind")
    if not all(math.isfinite(v) for v in bounds):
        raise ValueError("transformed shape bounds overflow")
    return bounds


def hypothetical_geometry_report(shape: Shape, matrix: tuple[float, ...]) -> dict:
    """Explicitly unverified geometry suitable for *private* candidate audits."""
    result = affine_diagnostics(matrix)
    result["hypothetical_aabb"] = hypothetical_shape_aabb(shape, matrix)
    result["association_confirmed"] = False
    result["physical_collision_confirmed"] = False
    result["interpretation"] = (
        "Unverified local-shape/world-object pairing; AABB is mathematical "
        "only, not a collidable region or proof of a game-world scale."
    )
    return result
