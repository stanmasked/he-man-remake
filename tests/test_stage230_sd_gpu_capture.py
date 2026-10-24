"""Stage230 SD capture verifier tests. Entirely invented data: no GPU execution."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "tools" / "verify_stage230_sd_gpu_capture.py"
spec = importlib.util.spec_from_file_location("stage230_sd", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

NRO = bytes(16) + b"NRO0" + b"synthetic-not-a-working-nro"
META = {
    "schema": "stage230-sd-capture-v1", "source_kind": "real_runtime",
    "runtime": "gpu_capable_emulator", "gpu_execution_observed": True,
    "command": "synthetic-test-not-actually-run",
    "runner_exit_code": 0, "nro_sha256": hashlib.sha256(NRO).hexdigest(),
}
RECEIPT = "STAGE230_GPU_READBACK width=16 height=8 bytes=512 pixels=128 mismatches=0\n"


class Stage230Tests(unittest.TestCase):
    def test_fixture_boundary(self):
        self.assertEqual(len(mod.fixture()), 512)
        self.assertEqual(mod.fixture()[0:4], bytes([0, 0, 0, 255]))
        self.assertEqual(mod.fixture()[36:40], bytes([0, 0, 0, 255]))
        self.assertEqual(mod.fixture()[32:36], bytes([160, 0, 8, 255]))

    def test_synthetic_positive_is_not_gpu_attestation(self):
        result = mod.check(mod.fixture(), RECEIPT, NRO, META, 0)
        self.assertFalse(result["hardware_execution_independently_attested"])
        self.assertEqual(result["status"], "submitted_sd_capture_bytes_match")

    def test_truncated_oversized_and_corrupt_pixels(self):
        for pixels in [b"", mod.fixture()[:-1], mod.fixture()+b"\0",
                       b"\0"*512]:
            with self.subTest(size=len(pixels)), self.assertRaises(mod.CaptureError):
                mod.check(pixels, RECEIPT, NRO, META, 0)

    def test_receipt_missing_stale_and_bad_mismatch(self):
        for receipt in ["", RECEIPT + RECEIPT, RECEIPT.replace("bytes=512", "bytes=256"),
                        RECEIPT.replace("mismatches=0", "mismatches=4"), "garbage\n"]:
            with self.subTest(receipt=receipt[:40]), self.assertRaises(mod.CaptureError):
                mod.check(mod.fixture(), receipt, NRO, META, 0)

    def test_wrong_nro_hash_and_exit(self):
        for args in [
            (NRO, dict(META, nro_sha256="0"*64), 0),
            (b"\0"*20, META, 0),
            (NRO, META, 1),
            (NRO, dict(META, runner_exit_code=1), 0),
        ]:
            with self.subTest(args=args[2]), self.assertRaises(mod.CaptureError):
                mod.check(mod.fixture(), RECEIPT, *args)

    def test_spoofed_cpu_or_fixture_metadata(self):
        for field, val in [
            ("runtime", "cpu_only"), ("source_kind", "synthetic_fixture"),
            ("gpu_execution_observed", False), ("schema", "wrong"),
            ("command", ""),
        ]:
            with self.subTest(field=field), self.assertRaises(mod.CaptureError):
                mod.check(mod.fixture(), RECEIPT, NRO, dict(META, **{field: val}), 0)


if __name__ == "__main__":
    unittest.main()
