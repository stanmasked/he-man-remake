"""Frame-by-frame C99 integrated packed-mask motion versus Python slope physics.

Tests use only independently authored synthetic wedges; no original game data.
"""
import csv
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from heman_tools.body_physics import Body, BodyConfig
from heman_tools.mask_physics import CollisionMask, EMPTY, MaskedGrid
from heman_tools.slope_physics import SlopeConfig, step_body_slopes

ROOT = Path(__file__).resolve().parents[1]


class NativeMaskGameplayParity(unittest.TestCase):
    def test_synthetic_slope_up_down_26_frames(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('C99 compiler unavailable')
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'trace_slope_game'
            subprocess.run([compiler, '-std=c99', '-O2', '-Wall', '-Wextra',
                            '-Werror', '-pedantic', '-I' + str(ROOT/'native/include'),
                            str(ROOT/'native/src/heman_core.c'),
                            str(ROOT/'native/src/heman_mask.c'),
                            str(ROOT/'native/tests/trace_slope_game.c'),
                            '-lm', '-o', str(exe)], check=True,
                           capture_output=True, text=True, timeout=30)
            out = subprocess.run([str(exe)], check=True, capture_output=True,
                                 text=True, timeout=15).stdout
        native = list(csv.DictReader(io.StringIO(out)))
        self.assertEqual(len(native), 26)
        n = 16
        wedge = CollisionMask(n, tuple(sum(1 << x for x in range(n)
                                           if y >= n-x-1) for y in range(n)))
        square = CollisionMask(n, (65535,)*n)
        grid = MaskedGrid(3,3,n,(1,2)+(EMPTY,)*7,{1:wedge,2:square})
        cfg = BodyConfig(half_width=.4,height=5,horizontal_speed=60,
                         gravity=1200,jump_speed=100,max_fall_speed=700)
        slope = SlopeConfig(max_rise=3,max_drop=3)
        actor = Body(2,13)
        for i,row in enumerate(native):
            axis = 0 if i < 1 else 1 if i < 12 else -1 if i < 22 else 0
            actor = step_body_slopes(actor,grid,axis,False,1/60,cfg,slope)
            self.assertEqual(int(row['frame']),i+1)
            for field,py in [('grounded',actor.grounded),
                             ('wall_hit',actor.wall_hit),
                             ('ceiling_hit',actor.ceiling_hit)]:
                self.assertEqual(int(row[field]),int(py),(i,field))
            for field,py in [('x',actor.x),('feet_y',actor.feet_y),
                             ('vy',actor.vertical_speed)]:
                self.assertAlmostEqual(float(row[field]),py,delta=.001,
                                       msg=(i,field))


if __name__=='__main__':
    unittest.main()
