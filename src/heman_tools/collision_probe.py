"""Opt-in private diagnostic: user-owned IPA maps + collision atlas, no export."""
import argparse
import io
import json
from pathlib import Path
import zipfile

from .mask_atlas import extract_masks_from_alpha
from .mask_physics import Actor, MaskedGrid, step_actor
from .tilemap import parse_tilemap


def private_probe(ipa: Path, *, map_name: str = 'MUMap1-1.map',
                  x: float = 50, start_y: float = 0, ticks: int = 240) -> dict:
    """Return aggregate diagnostics, never source image/map bytes.

    Pillow is imported only here; GitHub Actions does not need it.
    Physical masks derived from image alpha are provisional, not proven to
    match the game's runtime collision engine.
    """
    if '/' in map_name or '\\' in map_name or not map_name.endswith('.map'):
        raise ValueError('map_name must be a simple map basename')
    if not 1 <= ticks <= 3600:
        raise ValueError('ticks must be between 1 and 3600')
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('Install Pillow locally to read privately held collision texture') from exc
    prefix = 'Payload/MOTU.app/screen-med/'
    with zipfile.ZipFile(ipa) as archive:
        m = parse_tilemap(archive.read(prefix + 'maps/' + map_name))
        layer = m.layer('collision')
        raw = archive.read(prefix + 'textures/collisionTiles.png')
    if layer.tile_width != layer.tile_height:
        raise ValueError('non-square tile map is not supported by the prototype')
    if not layer.atlases or 'collision' not in layer.atlases:
        raise ValueError('collision atlas is not referenced by this layer')
    collision_atlas_index = layer.atlases.index('collision')
    for tile, atlas in zip(layer.tile_ids, layer.atlas_ids):
        if tile != 65535 and atlas != collision_atlas_index:
            raise ValueError('non-collision texture used in occupied collision layer cell')
    im = Image.open(io.BytesIO(raw)).convert('RGBA')
    used = set(layer.tile_ids) - {65535}
    masks = extract_masks_from_alpha(im.width, im.height, im.getchannel('A').tobytes(),
                                     layer.tile_width, used)
    grid = MaskedGrid(layer.columns, layer.rows, layer.tile_width, layer.tile_ids, masks)
    actor = Actor(x, start_y)
    for _ in range(ticks):
        actor = step_actor(actor, grid, 0, False, 1/60)
    return {
        'map': map_name,
        'grid': [layer.columns, layer.rows],
        'tile_size': layer.tile_width,
        'occupied_cells': layer.occupied_count,
        'tile_pixel_fill': {str(k): sum(row.bit_count() for row in mask.rows)
                            for k, mask in sorted(masks.items())},
        'probe': {'x': x, 'start_y': start_y, 'ticks': ticks,
                  'feet_y': round(actor.feet_y, 3), 'grounded': actor.grounded},
        'caveat': 'Alpha is a working collision approximation; NOT established original-game physics.',
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Local-only pixel mask and landing experiment')
    p.add_argument('--ipa', required=True, type=Path)
    p.add_argument('--map', default='MUMap1-1.map')
    p.add_argument('--x', type=float, default=50)
    p.add_argument('--start-y', type=float, default=0)
    p.add_argument('--ticks', type=int, default=240)
    p.add_argument('--out', type=Path, help='write local_reports/ private JSON')
    args = p.parse_args(argv)
    result = private_probe(args.ipa, map_name=args.map, x=args.x,
                           start_y=args.start_y, ticks=args.ticks)
    out = json.dumps(result, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out, encoding='utf-8')
        print(f'Private report written to {args.out}')
    else:
        print(out, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
