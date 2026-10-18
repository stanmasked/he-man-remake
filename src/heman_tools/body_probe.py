"""Local-only diagnostics for approximate player-body physics over iOS tiles.

All original game data remain on the user's machine. CI drives the pure script
runner against synthetic fixtures; the IPA-specific command requires Pillow.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import zipfile

from .body_physics import Body, BodyConfig, step_body
from .mask_atlas import extract_masks_from_alpha
from .mask_physics import MaskedGrid
from .tilemap import parse_tilemap


def run_body_script(grid: MaskedGrid, *, x: float, feet_y: float,
                    ticks: int, axis: float = 0.0,
                    jump_tick: int | None = None,
                    config: BodyConfig = BodyConfig()) -> dict:
    """Drive a deterministic finite host-side test without exposing assets."""
    if not isinstance(ticks, int) or not 1 <= ticks <= 3600:
        raise ValueError('ticks out of range')
    if jump_tick is not None and (not isinstance(jump_tick, int) or not 0 <= jump_tick < ticks):
        raise ValueError('jump_tick out of range')
    state = Body(x, feet_y)
    wall_ticks = ceiling_ticks = grounded_ticks = landing_events = 0
    old_grounded = False
    for tick in range(ticks):
        state = step_body(state, grid, axis, tick == jump_tick, 1/60, config)
        wall_ticks += state.wall_hit
        ceiling_ticks += state.ceiling_hit
        grounded_ticks += state.grounded
        landing_events += state.grounded and not old_grounded
        old_grounded = state.grounded
    return {
        'ticks': ticks,
        'final_x': round(state.x, 4),
        'final_feet_y': round(state.feet_y, 4),
        'grounded': state.grounded,
        'wall_contact_ticks': wall_ticks,
        'ceiling_contact_ticks': ceiling_ticks,
        'grounded_ticks': grounded_ticks,
        'landings': landing_events,
        'note': 'Independent experimental full-body mask physics, NOT the original iOS engine.',
    }


def local_ipa_body_probe(ipa: Path, *, map_name: str = 'MUMap1-1.map',
                         x: float = 50.0, feet_y: float = 0.0,
                         ticks: int = 240, axis: float = 0.0,
                         jump_tick: int | None = None) -> dict:
    if '/' in map_name or '\\' in map_name or not map_name.endswith('.map'):
        raise ValueError('invalid map basename')
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('Pillow must be installed locally for image decoding') from exc
    prefix = 'Payload/MOTU.app/screen-med/'
    with zipfile.ZipFile(ipa, 'r') as archive:
        map_info = archive.getinfo(prefix + 'maps/' + map_name)
        texture_info = archive.getinfo(prefix + 'textures/collisionTiles.png')
        if map_info.file_size > 16_000_000 or texture_info.file_size > 4_000_000:
            raise ValueError('game source entry exceeds safety bound')
        layer = parse_tilemap(archive.read(map_info)).layer('collision')
        image = Image.open(BytesIO(archive.read(texture_info))).convert('RGBA')
    if layer.tile_width != layer.tile_height:
        raise ValueError('non-square tile unsupported')
    if 'collision' not in layer.atlases:
        raise ValueError('collision atlas not present')
    collision_atlas_id = layer.atlases.index('collision')
    if any(t != 65535 and a != collision_atlas_id for t, a in zip(layer.tile_ids, layer.atlas_ids)):
        raise ValueError('occupied tile belongs to another atlas')
    masks = extract_masks_from_alpha(image.width, image.height, image.getchannel('A').tobytes(),
                                     layer.tile_width, set(layer.tile_ids) - {65535})
    grid = MaskedGrid(layer.columns, layer.rows, layer.tile_width, layer.tile_ids, masks)
    report = run_body_script(grid, x=x, feet_y=feet_y, ticks=ticks,
                             axis=axis, jump_tick=jump_tick)
    return {'map': map_name, 'grid': [layer.columns, layer.rows],
            'occupied_cells': layer.occupied_count, 'script': report}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Local full-body collision diagnostic (never uploads game data)')
    p.add_argument('--ipa', type=Path, required=True)
    p.add_argument('--map', default='MUMap1-1.map')
    p.add_argument('--x', type=float, default=50.0)
    p.add_argument('--feet-y', type=float, default=0.0)
    p.add_argument('--ticks', type=int, default=240)
    p.add_argument('--axis', type=float, default=0.0)
    p.add_argument('--jump-tick', type=int)
    p.add_argument('--out', type=Path, help='optional private local_reports output')
    args = p.parse_args(argv)
    report = local_ipa_body_probe(args.ipa, map_name=args.map, x=args.x,
                                  feet_y=args.feet_y, ticks=args.ticks,
                                  axis=args.axis, jump_tick=args.jump_tick)
    output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding='utf-8')
        print(f'Private diagnostics saved to {args.out}')
    else:
        print(output, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
