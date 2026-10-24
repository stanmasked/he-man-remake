"""Stage232 DKSH bounds tests on invented binaries; no GPU execution."""
import importlib.util
from pathlib import Path
import struct
import unittest

mod_path=Path(__file__).resolve().parents[1]/"tools"/"verify_stage232_dksh_loader.py"
spec=importlib.util.spec_from_file_location("stage232_layout",mod_path)
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def shader(stage: int = 0, *, hdr: int = 24, ctrl: int = 256,
           code: int = 256, off: int = 24, count: int = 1,
           entry: int = 48) -> bytes:
    raw=bytearray(512)
    struct.pack_into("<6I",raw,0, v.MAGIC,hdr,ctrl,code,off,count)
    if 0 <= off <= len(raw)-24:
        struct.pack_into("<6I",raw,off,stage,entry,4,0,0,0)
    return bytes(raw)


class Stage232Tests(unittest.TestCase):
    def setUp(self):
        self.vertex=shader(0)
        self.frag=shader(1)

    def test_valid_bundled_layout(self):
        result=v.verify_pair(self.vertex,self.frag)
        self.assertEqual(result["code_slots"],[[0,512],[4096,4608]])
        self.assertEqual(result["unusable_tail_bytes"],0x400)
        self.assertFalse(result["hardware_gpu_execution_verified"])

    def assert_bad(self, vertex=None, fragment=None, **kw):
        with self.assertRaises(v.ShaderLayoutError):
            v.verify_pair(self.vertex if vertex is None else vertex,
                          self.frag if fragment is None else fragment, **kw)

    def test_bad_magic_header_or_count(self):
        self.assert_bad(vertex=b"oops"+self.vertex[4:])
        self.assert_bad(vertex=shader(hdr=28))
        self.assert_bad(vertex=shader(count=0))
        self.assert_bad(vertex=shader(count=2))

    def test_wrong_stage_and_entrypoint(self):
        self.assert_bad(vertex=shader(stage=1))
        self.assert_bad(fragment=shader(stage=0))
        self.assert_bad(vertex=shader(entry=256))

    def test_alignment_and_overflow(self):
        self.assert_bad(vertex=shader(ctrl=255))
        self.assert_bad(vertex=shader(code=255))
        self.assert_bad(vertex=shader(ctrl=4096))
        self.assert_bad(vertex=shader(code=4096))
        self.assert_bad(vertex=shader(off=240))

    def test_truncated_and_trailing(self):
        self.assert_bad(vertex=self.vertex[:-1])
        self.assert_bad(vertex=self.vertex+b"x")
        self.assert_bad(vertex=b"")
        self.assert_bad(fragment=self.frag[:23])

    def test_code_mem_unusable_tail_and_overlaps(self):
        self.assert_bad(memblock_size=4608)
        self.assert_bad(offsets=(0,256))
        self.assert_bad(offsets=(0,3841))
        self.assert_bad(offsets=(0,-256))
        self.assert_bad(offsets=(0,12288))

    def test_detect_garbage_header_in_control(self):
        self.assert_bad(vertex=shader(off=240))
        self.assert_bad(vertex=shader(off=0))

    def test_known_sample_sizes_match_sdk(self):
        for name, data, expected in [("vertex",self.vertex,0),("fragment",self.frag,1)]:
            with self.subTest(name=name):
                result=v.inspect(data,name)
                self.assertEqual(result["control_bytes"],256)
                self.assertEqual(result["code_bytes"],256)
                self.assertEqual(struct.unpack_from("<I",data,24)[0],expected)


if __name__ == "__main__":
    unittest.main()
