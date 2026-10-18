"""Audit all .shape entries in a local iOS IPA without extracting game assets."""
import argparse
from collections import Counter
import json
from pathlib import Path
import zipfile

from .lvl import LevelFormatError
from .shapes import parse_shape


def audit_shapes(ipa: Path, screen: str = 'screen-med') -> dict:
    if screen not in ('screen-med', 'screen-xlarge'):
        raise ValueError('screen must be screen-med or screen-xlarge')
    prefix = f'Payload/MOTU.app/{screen}/geometry/'
    counter = Counter()
    refs = 0
    total_vertices = 0
    with zipfile.ZipFile(ipa, 'r') as archive:
        for info in archive.infolist():
            if not info.filename.startswith(prefix) or not info.filename.endswith('.shape'):
                continue
            if info.file_size > 1024 * 1024:
                raise LevelFormatError('oversized .shape entry')
            shape = parse_shape(archive.read(info))
            counter[shape.kind] += 1
            refs += shape.reference is not None
            total_vertices += len(shape.vertices)
    return {'screen': screen, 'total': sum(counter.values()),
            'polygons': counter['polygon'], 'circles': counter['circle'],
            'referenced': refs, 'total_polygon_vertices': total_vertices,
            'note': 'Shapes are local-space primitives; their in-game function and placement are not inferred.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only .shape header scan of local purchased iOS archive')
    parser.add_argument('--ipa', type=Path, required=True)
    parser.add_argument('--screen', choices=('screen-med', 'screen-xlarge'), default='screen-med')
    parser.add_argument('--out', type=Path, help='optional local_reports/*.json path')
    args = parser.parse_args(argv)
    report = audit_shapes(args.ipa, args.screen)
    data = json.dumps(report, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data, encoding='utf-8')
        print(f"Checked {report['total']} shape definitions; private report: {args.out}")
    else:
        print(data, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
