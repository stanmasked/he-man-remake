"""Host-only invented Stage229 captures: never count tests as GPU execution."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

module = Path(__file__).resolve().parents[1] / "tools" / "verify_stage229_gpu_readback.py"
spec = importlib.util.spec_from_file_location("stage229_verifier", module)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

NRO = b"\0" * 16 + b"NRO0" + b"host-invented-NRO-not-a-real-binary"
META = {
    "schema": "stage229-gpu-run-v1",
    "source_kind": "real_runtime",
    "runtime": "gpu_capable_emulator",
    "gpu_execution_observed": True,
    "stdout_captured": True,
    "runner_exit_code": 0,
    "command": "example-only-do-not-claim-runtime",
    "nro_sha256": hashlib.sha256(NRO).hexdigest(),
}


def invented_log(pixels=None, *, rows=None, end=0, old=0):
    if pixels is None:
        pixels = v.expected_pixels()
    if rows is None:
        rows = list(range(v.HEIGHT))
    result = ["guest output before marker",
              "STAGE229_GPU_READBACK_BEGIN width=16 height=8 bytes=512"]
    for y in rows:
        result.append(f"STAGE229_GPU_READBACK_ROW y={y} rgba="
                      + pixels[y * 64:(y + 1) * 64].hex())
    result.extend([f"STAGE229_GPU_READBACK_END mismatches={end}",
                   f"STAGE228_GPU_QUAD_READBACK pixels=128 mismatches={old}",
                   "guest output after marker"])
    return "\n".join(result)


class Stage229EvidenceTests(unittest.TestCase):
    def test_reference_exact_size_and_padding(self):
        raw = v.expected_pixels()
        self.assertEqual(len(raw), 512)
        self.assertEqual(raw[:4], bytes((0, 0, 0, 255)))
        self.assertEqual(raw[8*4:9*4], bytes((160, 0, 8, 255)))
        self.assertEqual(raw[9*4:10*4], bytes((0, 0, 0, 255)))
        self.assertEqual(raw[5*64:5*64+4], bytes((0, 0, 0, 255)))

    def test_invented_good_log_is_only_structurally_valid(self):
        receipt = v.verify_capture(invented_log(), 0, NRO, dict(META))
        self.assertEqual(receipt["result"], "submitted_capture_pixels_match")
        self.assertFalse(receipt["hardware_execution_independently_attested"])
        self.assertEqual(receipt["pixel_count"], 128)

    def check_bad(self, log=None, exit_code=0, nro=NRO, meta=None):
        with self.assertRaises(v.EvidenceError):
            v.verify_capture(invented_log() if log is None else log,
                             exit_code, nro, dict(META) if meta is None else meta)

    def test_missing_marker_and_duplicate(self):
        good = invented_log()
        self.check_bad(good.replace("STAGE229_GPU_READBACK_BEGIN", "REMOVED"))
        self.check_bad(good + "\n" + good.split("\n")[1])

    def test_missing_reordered_duplicate_rows(self):
        self.check_bad(invented_log(rows=list(range(7))))
        self.check_bad(invented_log(rows=[1, 0] + list(range(2, 8))))
        self.check_bad(invented_log(rows=[0, 0] + list(range(2, 8))))

    def test_wrong_pixel_source_even_if_guest_claims_zero_errors(self):
        buf = bytearray(v.expected_pixels())
        buf[14] ^= 0x20
        self.check_bad(invented_log(pixels=buf, end=0, old=0))

    def test_bad_dimensions_and_truncated_pixels(self):
        self.check_bad(invented_log().replace("width=16", "width=9"))
        self.check_bad(invented_log().replace("bytes=512", "bytes=256"))
        self.check_bad(invented_log().replace("rgba=" + v.expected_pixels()[:64].hex(),
                                             "rgba=ab"))

    def test_guest_failure_and_status_failure(self):
        self.check_bad(invented_log(end=1))
        self.check_bad(invented_log(old=1))
        self.check_bad(exit_code=2)
        meta = dict(META, runner_exit_code=1)
        self.check_bad(meta=meta)

    def test_untrusted_runtime_claim(self):
        for meta in (dict(META, source_kind="synthetic_fixture"),
                     dict(META, runtime="cpu_only_emulator"),
                     dict(META, gpu_execution_observed=False),
                     dict(META, stdout_captured=False),
                     dict(META, command=""),
                     dict(META, schema="wrong")):
            with self.subTest(meta=meta):
                self.check_bad(meta=meta)

    def test_sha256_and_nro_header_mismatch(self):
        self.check_bad(meta=dict(META, nro_sha256="0" * 64))
        self.check_bad(nro=b"\0" * 32)

    def test_bounded_log_and_sequence(self):
        self.check_bad("x" * 65537)
        good = invented_log().splitlines()
        self.check_bad("\n".join([good[0], good[-2]] + good[1:-2] + [good[-1]]))
        self.check_bad(invented_log().replace("STAGE229_GPU_READBACK_END",
                                             "STAGE229_GPU_READBACK_ROW y=7 rgba=ffff\n"
                                             "STAGE229_GPU_READBACK_END"))


if __name__ == "__main__":
    unittest.main()
