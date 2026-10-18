"""Read map layer metadata from a local iOS IPA without extracting assets."""
import argparse
import json
from pathlib import Path
import zipfile

from .tilemap import MAX_FILE, TileMapFormatError, parse_tilemap


def inspect_map(ipa: Path, name: str, screen: str = 'screen-med') -> dict:
    if '/' in name or '\\' in name or not name.endswith('.map') or not name[:-4]:
        raise ValueError('map must be a simple .map basename')
    if screen not in ('screen-med', 'screen-xlarge'):
        raise ValueError('unknown screen group')
    entry = f'Payload/MOTU.app/{screen}/maps/{name}'
    with zipfile.ZipFile(ipa, 'r') as archive:
        info = archive.getinfo(entry)
        if info.file_size > MAX_FILE:
            raise TileMapFormatError('oversized input map')
        parsed = parse_tilemap(archive.read(info))
    return {
        'file': name, 'screen': screen,
        'layers': [{'name': l.name, 'columns': l.columns, 'rows': l.rows,
                    'tile_width': l.tile_width, 'tile_height': l.tile_height,
                    'atlas_count': len(l.atlases), 'occupied_cells': l.occupied_count}
                   for l in parsed.layers],
        'disclaimer': 'Layer names are preserved; occupied tiles are NOT yet verified physical collision surfaces.',
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Inspect original iOS map structure locally')
    p.add_argument('--ipa', type=Path, required=True)
    p.add_argument('--map', dest='name', required=True)
    p.add_argument('--screen', choices=['screen-med', 'screen-xlarge'], default='screen-med')
    p.add_argument('--out', type=Path, help='optional local_reports/ JSON output')
    args = p.parse_args(argv)
    report = inspect_map(args.ipa, args.name, args.screen)
    data = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data, encoding='utf-8')
        print(f"Analysed {len(report['layers'])} layers; local report at {args.out}")
    else:
        print(data, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
