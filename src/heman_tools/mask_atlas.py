"""Tile masks from caller-supplied alpha pixels (never source-art assets)."""
from .mask_physics import CollisionMask


def extract_masks_from_alpha(width: int, height: int, alpha: bytes,
                             tile_size: int, indices: set[int], threshold: int = 128) -> dict[int, CollisionMask]:
    """Extract row-major tile masks from already decoded image alpha bytes.

    PNG decoding is left to the private local caller; this module has no
    dependency on copyrighted pixels or third-party libraries.
    """
    if not 1 <= tile_size <= 64 or not 0 < width <= 8192 or not 0 < height <= 8192:
        raise ValueError('invalid image/tile size')
    if width % tile_size or height % tile_size or len(alpha) != width * height:
        raise ValueError('image does not tile evenly or alpha data are malformed')
    columns = width // tile_size
    count = columns * (height // tile_size)
    if any(not isinstance(index, int) or index < 0 or index >= count for index in indices):
        raise ValueError('tile index exceeds alpha atlas')
    masks = {}
    for index in indices:
        tx = (index % columns) * tile_size
        ty = (index // columns) * tile_size
        rows = [alpha[(ty + y)*width+tx:(ty+y)*width+tx+tile_size]
                for y in range(tile_size)]
        masks[index] = CollisionMask.from_alpha(rows, threshold=threshold)
    return masks
