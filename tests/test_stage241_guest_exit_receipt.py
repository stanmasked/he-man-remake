"""Stage241 negative tests are synthetic only; no emulator/GPU is executed."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage241_guest_exit_receipt as m

NONCE="a"*32
GOOD=f"STAGE241_GUEST_EXIT nonce={NONCE} code=0\n".encode("ascii")


class GuestExitTests(unittest.TestCase):
    def test_exact_good_receipt_is_only_cpu_side_diagnostic(self):
        result=m.check_guest_exit(GOOD,NONCE)
        self.assertEqual(result["status"],"valid")
        self.assertEqual(result["guest_exit_code"],0)
        self.assertTrue(result["guest_reported_success"])
        self.assertEqual(result["sha256"],hashlib.sha256(GOOD).hexdigest())
        self.assertFalse(result["runtime_gpu_execution_attested"])

    def test_missing_nonzero_and_stale_nonce_fail(self):
        absent=m.check_guest_exit(None,NONCE)
        self.assertFalse(absent["guest_reported_success"])
        self.assertEqual(absent["status"],"missing")
        bad=m.check_guest_exit(
            f"STAGE241_GUEST_EXIT nonce={NONCE} code=25\n".encode(),NONCE)
        self.assertEqual(bad["guest_exit_code"],25)
        self.assertFalse(bad["guest_reported_success"])
        stale=m.check_guest_exit(GOOD,"b"*32)
        self.assertEqual(stale["status"],"nonce_mismatch")
        self.assertFalse(stale["guest_reported_success"])

    def test_malformed_and_oversized_receipts_fail(self):
        invalid=[
            b"",
            GOOD[:-1],
            GOOD+b"\n",
            GOOD.replace(b"code=0",b"code=00"),
            GOOD.replace(b"code=0",b"code=-1"),
            GOOD.replace(b"code=0",b"code=1000"),
            GOOD.replace(b"nonce=",b"NONCE="),
            GOOD.replace(b"a"*32,b"A"*32),
        ]
        for data in invalid:
            with self.subTest(data=data):
                self.assertFalse(m.check_guest_exit(data,NONCE)["guest_reported_success"])
        self.assertEqual(m.check_guest_exit(b"x"*129,NONCE)["status"],
                         "oversized_or_unreadable")

    def test_nonce_format_is_strict(self):
        for nonce in ("", "A"*32, "a"*31, "z"*32):
            with self.subTest(nonce=nonce),self.assertRaises(ValueError):
                m.check_guest_exit(GOOD,nonce)

    def test_private_file_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"guest_exit.txt"
            self.assertEqual(m.inspect_guest_exit_file(path,NONCE)["status"],
                             "missing")
            path.write_bytes(GOOD)
            self.assertTrue(m.inspect_guest_exit_file(path,NONCE)["guest_reported_success"])
            path.write_bytes(b"x"*500)
            self.assertEqual(m.inspect_guest_exit_file(path,NONCE)["status"],
                             "oversized_or_unreadable")

    def test_guest_source_resets_stale_and_saves_exit_after_runner(self):
        cpp=(Path(__file__).resolve().parents[1]/
             "switch_gpu_png"/"source"/"main.cpp").read_text(encoding="utf-8")
        self.assertIn('"sdmc:/switch/heman-stage230/guest_exit.txt"',cpp)
        self.assertIn('"sdmc:/switch/heman-stage230/guest_exit.tmp"',cpp)
        self.assertIn("const int guestCode=runStage241Guest(argc,argv);",cpp)
        self.assertIn("if(s_stage231Nonce[0] && !saveStage241GuestExit(guestCode))",cpp)
        self.assertEqual(cpp.count('STAGE241_GUEST_EXIT nonce=%s code=%d'),1)


if __name__=="__main__":
    unittest.main()
