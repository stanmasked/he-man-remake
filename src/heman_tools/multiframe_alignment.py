"""Private, evidence-only cross-frame consistency check for stationary landmarks.

Fitted screen offsets may vary with the camera, but a strict same-scale
hypothesis must survive multiple captures. No original-game behavior inferred.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .frame_alignment import fit_single_frame, _private_path

_MAX_FRAMES = 32
_MAX_JSON = 1_000_000


def compare_stationary_frames(data: dict, *, max_residual_px: float = 2.0,
                              max_relative_scale_drift: float = 0.02) -> dict:
    """Reject inconsistent scales or changed identities across 2–32 captures.

    Each frame MUST observe the same four or more verified stationary physical
    landmarks, identified with the same ID and *identical level coordinates*.
    A different camera offset per frame is allowed; zoom and axis flips aren't.
    """
    if not isinstance(data, dict):
        raise ValueError('expected an object containing frames')
    frames = data.get('frames')
    if not isinstance(frames, list) or not 2 <= len(frames) <= _MAX_FRAMES:
        raise ValueError('expected 2–32 frame reports')
    if (isinstance(max_relative_scale_drift, bool) or
            not isinstance(max_relative_scale_drift, (float, int)) or
            not math.isfinite(max_relative_scale_drift) or
            not 0 < max_relative_scale_drift <= 0.2):
        raise ValueError('invalid relative scale tolerance')
    ids_seen: set[str] = set()
    reference: dict[str, tuple[float, float]] | None = None
    fitted = []
    for frame in frames:
        fit = fit_single_frame(frame, max_residual_px=max_residual_px)
        frame_id = fit['frame_id']
        if frame_id in ids_seen:
            raise ValueError('duplicate frame ID')
        ids_seen.add(frame_id)
        current = {
            entry['id']: tuple(float(v) for v in entry['level_xy'])
            for entry in frame['anchors']
        }
        if reference is None:
            reference = current
        elif current != reference:
            raise ValueError('cross-frame landmark IDs or level positions differ')
        fitted.append(fit)
    assert reference is not None
    base = fitted[0]['level_to_screen_scale']
    drifts = []
    for row in fitted:
        scales = row['level_to_screen_scale']
        relative = [abs((actual - original) / original)
                    for original, actual in zip(base, scales)]
        if not all(math.isfinite(v) for v in relative):
            raise ValueError('non-finite relative scale drift')
        if max(relative) > max_relative_scale_drift:
            raise ValueError('cross-frame scale drift exceeds tolerance')
        drifts.append(relative)
    return {
        'frame_ids': [r['frame_id'] for r in fitted],
        'stationary_anchor_count': len(reference),
        'reference_scale': base,
        'frame_offsets_px': [r['level_to_screen_offset_px'] for r in fitted],
        'frame_max_residual_px': [r['max_residual_px'] for r in fitted],
        'max_relative_scale_drift': max(max(v) for v in drifts),
        'allowed_relative_scale_drift': float(max_relative_scale_drift),
        'consistent_under_axis_aligned_hypothesis': True,
        'authentic_camera_behavior_proven': False,
        'physical_units_verified': False,
        'shape_ownership_verified': False,
        'interpretation': (
            'Multiple-frame numeric consistency only; manually matched object '
            'identity, original camera model, parallax, 3D depth, collision '
            'and iOS physics remain unverified.'
        ),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--max-residual-px', type=float, default=2.0)
    p.add_argument('--max-relative-scale-drift', type=float, default=0.02)
    args = p.parse_args(argv)
    src = _private_path(args.frames)
    dst = _private_path(args.out)
    if src == dst:
        raise ValueError('input and output must not be the same file')
    if src.stat().st_size > _MAX_JSON:
        raise ValueError('input exceeds one megabyte')
    report = compare_stationary_frames(json.loads(src.read_text(encoding='utf-8')),
        max_residual_px=args.max_residual_px,
        max_relative_scale_drift=args.max_relative_scale_drift)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print('Compared synthetic or private multi-frame landmark fits; report stored locally.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
