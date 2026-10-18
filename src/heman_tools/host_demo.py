"""Keyboard-controlled host prototype (A/D, arrows, Space, R, Esc).

Runs on a synthetic asset-free course by default. --ipa reads purchased data
only on the user's own computer; neither game data nor previews are uploaded.
Tkinter and Pillow are optional, imported only in the paths requiring them.
"""
import argparse
from io import BytesIO
import json
import math
from pathlib import Path
from time import perf_counter
import zipfile

from .event_view import draw_event_overlay, event_overlay
from .body_physics import BodyConfig
from .mask_atlas import extract_masks_from_alpha
from .mask_physics import EMPTY, MaskedGrid
from .scene import SceneControls, SceneWorld, advance_scene, new_scene, synthetic_world
from .slope_physics import SlopeConfig
from .tilemap import parse_tilemap

TICK = 1 / 60


def load_private_world(ipa: Path, name: str = 'MUMap1-1.map',
                       *, spawn_x: float = 50.0, spawn_feet_y: float = 0.0) -> SceneWorld:
    if not name.endswith('.map') or not name[:-4] or '/' in name or '\\' in name:
        raise ValueError('map must be a bare .map filename')
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('Install Pillow locally to load private alpha masks') from exc
    prefix = 'Payload/MOTU.app/screen-med/'
    with zipfile.ZipFile(ipa) as archive:
        map_info = archive.getinfo(prefix + 'maps/' + name)
        image_info = archive.getinfo(prefix + 'textures/collisionTiles.png')
        if map_info.file_size > 16_000_000 or image_info.file_size > 4_000_000:
            raise ValueError('private game entry too large')
        layer = parse_tilemap(archive.read(map_info)).layer('collision')
        with Image.open(BytesIO(archive.read(image_info))) as image:
            picture = image.convert('RGBA')
        alpha = picture.getchannel('A').tobytes()
    if layer.tile_width != layer.tile_height:
        raise ValueError('unsupported non-square tiles')
    if 'collision' not in layer.atlases:
        raise ValueError('collision atlas not referenced')
    atlas = layer.atlases.index('collision')
    if any(t != EMPTY and a != atlas for t, a in zip(layer.tile_ids, layer.atlas_ids)):
        raise ValueError('unexpected collision atlas assignment')
    masks = extract_masks_from_alpha(picture.width, picture.height, alpha,
                                     layer.tile_width, set(layer.tile_ids) - {EMPTY})
    grid = MaskedGrid(layer.columns, layer.rows, layer.tile_width, layer.tile_ids, masks)
    return SceneWorld(grid, spawn_x, spawn_feet_y,
                      physics=BodyConfig(half_width=5, height=22),
                      slope=SlopeConfig(max_rise=6, max_drop=6))


def headless_replay(world: SceneWorld, ticks: int = 240) -> dict:
    """Reproduce CI movement without a window, animation assets or network."""
    if not isinstance(ticks, int) or not 1 <= ticks <= 3600:
        raise ValueError('headless replay ticks must be 1..3600')
    state = new_scene(world)
    for tick in range(ticks):
        controls = SceneControls(axis=1.0 if 40 <= tick < 140 else 0.0,
                                 jump=tick == 85)
        state = advance_scene(state, world, controls, TICK)
    return {'frames': state.frame, 'x': round(state.actor.x, 5),
            'feet_y': round(state.actor.feet_y, 5),
            'grounded': state.actor.grounded, 'respawns': state.respawns,
            'landings': state.landings,
            'camera_x': round(state.camera_x, 5),
            'camera_y': round(state.camera_y, 5),
            'disclaimer': 'Host physics simulation only, not authentic iOS mechanics or a Switch build.'}


def _mask_rects(mask):
    """Coalesce consecutive identical pixel runs for efficient canvas drawings."""
    active, rects = {}, []
    for y, bits in enumerate(mask.rows):
        spans = []
        x = 0
        while x < mask.size:
            if not bits & (1 << x):
                x += 1
                continue
            start = x
            while x < mask.size and bits & (1 << x):
                x += 1
            spans.append((start, x))
        new = {}
        for span in spans:
            if span in active:
                x0, y0, x1, _ = active[span]
                new[span] = (x0, y0, x1, y+1)
            else:
                new[span] = (span[0], y, span[1], y+1)
        rects.extend(r for span, r in active.items() if span not in new)
        active = new
    rects.extend(active.values())
    return tuple(rects)


def run_gui(world: SceneWorld, *, title: str, interactive_world=None) -> None:
    """Draw temporary art, drive movement at fixed 60Hz, follow character."""
    try:
        import tkinter as tk
    except ImportError as exc:
        raise RuntimeError('Tkinter is required for the optional desktop window') from exc
    root = tk.Tk()
    root.title(title)
    vw, vh = world.viewport_width, world.viewport_height
    canvas = tk.Canvas(root, width=vw, height=vh, bg='#0b192d', highlightthickness=0)
    canvas.pack()
    root.resizable(False, False)
    active = set()
    jump_requested = False
    reset_requested = False
    state = new_scene(world)
    interactive_state = None
    if interactive_world is not None:
        from .scene_interactions import new_interactive_scene
        interactive_state = new_interactive_scene(interactive_world)
        state = interactive_state.scene
    mesh = {tile: _mask_rects(mask) for tile, mask in world.grid.masks.items()}
    last = perf_counter()
    accumulator = 0.0

    def key_down(event):
        nonlocal jump_requested, reset_requested
        key = event.keysym.lower()
        if key == 'escape':
            root.destroy()
            return
        if key in {'space', 'up', 'w'} and key not in active:
            jump_requested = True
        if key == 'r' and key not in active:
            reset_requested = True
        active.add(key)

    def key_up(event):
        active.discard(event.keysym.lower())

    root.bind('<KeyPress>', key_down)
    root.bind('<KeyRelease>', key_up)
    root.bind('<FocusOut>', lambda _event: active.clear())

    def paint():
        canvas.delete('all')
        cx, cy = state.camera_x, state.camera_y
        canvas.create_rectangle(0, 0, vw, vh, fill='#101f38', outline='')
        tile_size = world.grid.tile_size
        x0, y0 = max(0, math.floor(cx/tile_size)), max(0, math.floor(cy/tile_size))
        x1 = min(world.grid.width, math.ceil((cx+vw)/tile_size)+1)
        y1 = min(world.grid.height, math.ceil((cy+vh)/tile_size)+1)
        for row in range(y0, y1):
            for col in range(x0, x1):
                tile = world.grid.tile_ids[row*world.grid.width+col]
                if tile == EMPTY:
                    continue
                sx, sy = col*tile_size-cx, row*tile_size-cy
                color = '#476e91' if tile == 5 else '#31998b'
                for rx0, ry0, rx1, ry1 in mesh[tile]:
                    canvas.create_rectangle(sx+rx0, sy+ry0, sx+rx1, sy+ry1,
                                            fill=color, outline='')
        actor = state.actor
        ax, ay = actor.x-cx, actor.feet_y-cy
        half, tall = world.physics.half_width, world.physics.height
        canvas.create_rectangle(ax-half, ay-tall, ax+half, ay,
                                fill='#fcd76c', outline='#101f38', width=2)
        canvas.create_oval(ax-4.4, ay-tall-6, ax+4.4, ay-tall+2,
                           fill='#f8bd70', outline='#101f38')
        if interactive_state is not None:
            draw_event_overlay(canvas, event_overlay(interactive_world, interactive_state),
                               width=vw, height=vh)
        canvas.create_text(12, 12, anchor='nw', fill='#f8fafc',
                           font=('Arial', 15, 'bold'),
                           text='HE-MAN REMAKE  ·  HOST PHYSICS PROTOTYPE')
        canvas.create_text(12, 37, anchor='nw', fill='#bbcfdf', font=('Arial', 11),
                           text='A/D or arrows: move   Space: jump   R: reset   Esc: quit')
        canvas.create_text(12, vh-26, anchor='nw', fill='#d8e6f4',
                           font=('Arial', 10),
                           text=f'frame {state.frame}   pos {actor.x:.1f}, {actor.feet_y:.1f}   '
                                f'grounded {actor.grounded}   respawns {state.respawns}')

    def frame():
        nonlocal last, accumulator, state, interactive_state, jump_requested, reset_requested
        if not root.winfo_exists():
            return
        now = perf_counter()
        accumulator = min(accumulator + max(0.0, now-last), 0.15)
        last = now
        steps = 0
        while accumulator >= TICK and steps < 6:
            axis = int('right' in active or 'd' in active) - int('left' in active or 'a' in active)
            controls = SceneControls(axis, jump_requested, reset_requested)
            if interactive_world is not None:
                from .scene_interactions import advance_interactive
                interactive_state = advance_interactive(interactive_state, interactive_world,
                                                          controls, TICK)
                state = interactive_state.scene
            else:
                state = advance_scene(state, world, controls, TICK)
            jump_requested = False
            reset_requested = False
            accumulator -= TICK
            steps += 1
        if steps == 6:
            accumulator = min(accumulator, TICK)
        paint()
        root.after(16, frame)

    root.focus_force()
    frame()
    root.mainloop()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Keyboard-playable host demo, not a Switch build')
    parser.add_argument('--ipa', type=Path, help='optional local purchased IPA')
    parser.add_argument('--map', default='MUMap1-1.map')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--interactions', action='store_true',
                        help='show synthetic events and gameplay HUD')
    parser.add_argument('--ticks', type=int, default=240)
    parser.add_argument('--out', type=Path, help='optional private replay JSON')
    args = parser.parse_args(argv)
    if args.interactions and args.ipa:
        parser.error('--interactions is only supported for the synthetic course')
    interactive_world = None
    if args.interactions:
        from .scene_interactions import synthetic_interactive_world
        interactive_world = synthetic_interactive_world()
        world = interactive_world.scene
    else:
        world = load_private_world(args.ipa, args.map) if args.ipa else synthetic_world()
    if args.headless:
        if args.interactions:
            from .events_demo import replay as replay_events
            report = replay_events(args.ticks)
        else:
            report = headless_replay(world, args.ticks)
        result = json.dumps(report, indent=2) + '\n'
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(result, encoding='utf-8')
            print(f'Local replay report: {args.out}')
        else:
            print(result, end='')
    else:
        run_gui(world, title='He-Man Remake — Host Physics Prototype',
                interactive_world=interactive_world)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
