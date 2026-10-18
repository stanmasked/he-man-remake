"""Independent C99 vs Python parity on synthetic, non-copyrighted input.

The native core currently supports rectangular full-tile physics, NOT the
Python slope/one-way model. Scenarios compare only the common feature subset.
"""
import csv
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from heman_tools.body_physics import Body, BodyConfig, overlaps_body
from heman_tools.mask_physics import CollisionMask, EMPTY, MaskedGrid

ROOT = Path(__file__).resolve().parents[1]
W, H, TILE = 40, 20, 16
CFG = BodyConfig(half_width=5, height=22, horizontal_speed=120,
                 gravity=1200, jump_speed=420, max_fall_speed=1400)


def synthetic_world(kind):
    cells = [EMPTY] * (W * H)
    for col in range(W):
        cells[10*W + col] = 1
    spawn = 40.0
    if kind == 'wall':
        spawn = 180.0
        for row in range(6, 10):
            cells[row*W + 15] = 1
    elif kind == 'ceiling':
        for col in range(1, 18):
            cells[6*W + col] = 1
    elif kind == 'ledge':
        spawn = 160.0
        for col in range(13, W):
            cells[10*W + col] = EMPTY
    elif kind != 'flat':
        raise ValueError(kind)
    full = CollisionMask(TILE, (((1 << TILE)-1),)*TILE)
    return MaskedGrid(W,H,TILE,tuple(cells),{1:full}), spawn


def control(kind, i):
    if kind == 'flat': return (1.0 if 25 <= i < 120 else 0.0), i == 54
    if kind == 'wall': return (1.0 if i >= 15 else 0.0), i == 95
    if kind == 'ceiling': return 0.0, i == 30
    if kind == 'ledge': return (1.0 if i >= 20 else 0.0), False
    raise ValueError(kind)


def python_trace(kind):
    from heman_tools.body_physics import step_body
    grid, spawn = synthetic_world(kind)
    actor = Body(spawn,160)
    camera_x = camera_y = 0.0
    respawns=0
    trace=[]
    for i in range(180):
        axis,jump=control(kind,i)
        actor=step_body(actor,grid,axis,jump,1/60,CFG)
        if actor.feet_y > H*TILE + 80:
            respawns+=1
            actor=Body(spawn,160)
        tx=max(0.0,min(actor.x - 320*.42, W*TILE-320))
        ty=max(0.0,min(actor.feet_y-240*.64,H*TILE-240))
        camera_x=max(0.0,min(camera_x + (1/60)*10*(tx-camera_x), W*TILE-320))
        camera_y=max(0.0,min(camera_y + (1/60)*10*(ty-camera_y), H*TILE-240))
        trace.append(dict(frame=i+1,x=actor.x,feet_y=actor.feet_y,vy=actor.vertical_speed,
                grounded=int(actor.grounded),wall_hit=int(actor.wall_hit),
                ceiling_hit=int(actor.ceiling_hit),camera_x=camera_x,
                camera_y=camera_y,respawns=respawns))
    return trace


class NativeTraceParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('cc'):
            raise unittest.SkipTest('C99 compiler is required for native comparison')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.executable = Path(cls.tmp.name)/'trace_core'
        cmd=['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-pedantic',
             '-I'+str(ROOT/'native/include'),str(ROOT/'native/src/heman_core.c'),
             str(ROOT/'native/tests/trace_core.c'),'-lm','-o',str(cls.executable)]
        subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_shared_scenarios(self):
        for scenario in ('flat','wall','ceiling','ledge'):
            with self.subTest(scenario=scenario):
                stdout=subprocess.run([str(self.executable), scenario],check=True,
                                      text=True,capture_output=True,timeout=15).stdout
                native=list(csv.DictReader(io.StringIO(stdout)))
                reference=python_trace(scenario)
                self.assertEqual(len(native),180)
                for ix,(row,expected) in enumerate(zip(native,reference)):
                    for key in ('frame','grounded','wall_hit','ceiling_hit','respawns'):
                        self.assertEqual(int(row[key]), expected[key],
                                         (scenario,ix,key,row[key],expected[key]))
                    for key in ('x','feet_y','vy','camera_x','camera_y'):
                        self.assertAlmostEqual(float(row[key]),expected[key],delta=.035,
                              msg=(scenario,ix,key,float(row[key]),expected[key]))


class NativeMaskParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('cc'):
            raise unittest.SkipTest('C99 compiler is required for mask comparison')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.executable = Path(cls.tmp.name)/'trace_mask'
        cmd=['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-pedantic',
             '-I'+str(ROOT/'native/include'),str(ROOT/'native/src/heman_mask.c'),
             str(ROOT/'native/tests/trace_mask.c'),'-lm','-o',str(cls.executable)]
        subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_synthetic_wedges_match_python_pixel_semantics(self):
        wedge=CollisionMask(16,tuple((1<<(row+1))-1 for row in range(16)))
        full=CollisionMask(16,tuple([65535]*16))
        grid=MaskedGrid(2,2,16,(1,2,EMPTY,EMPTY),{1:wedge,2:full})
        stdout=subprocess.run([str(self.executable)],check=True,capture_output=True,
                              text=True,timeout=10).stdout
        rows=list(csv.DictReader(io.StringIO(stdout)))
        self.assertEqual(len(rows),32)
        for row in rows:
            x=int(row['x'])
            expected_y=grid.first_feet_contact(x,0,0,15)
            self.assertEqual(int(row['found']),int(expected_y is not None))
            self.assertEqual(int(row['contact_y']),expected_y)
            self.assertEqual(int(row['solid_y0']),int(grid.solid_at(x,0)))
            self.assertEqual(int(row['body_overlap']),
                             int(overlaps_body(grid,float(x),4,1,4)))


if __name__ == '__main__':
    unittest.main()
