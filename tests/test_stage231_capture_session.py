"""Stage231 anti-replay regressions. Entirely invented data, not GPU evidence."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / "tools" / "stage231_capture_session.py"
spec = importlib.util.spec_from_file_location("stage231_session", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

CHALLENGE = "a" * 31 + "0"
FAKE_NRO = bytes(16) + b"NRO0" + b"fake-not-executed"
RECEIPT = (
    "STAGE230_GPU_READBACK width=16 height=8 bytes=512 "
    f"pixels=128 mismatches=0 nonce={CHALLENGE}\n"
)


class Stage231SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.nro = root / "run.nro"
        self.nro.write_bytes(FAKE_NRO)
        self.sd = root / "sd"
        self.out = root / "owner-private"
        self.session = m.prepare(self.nro, self.sd, self.out, challenge=CHALLENGE)
        self.capture = m.sd_dir(self.sd)
        self.log = root / "runner.log"
        self.log.write_bytes(b"test-only fake runner log\n")
        self.status = root / "exit.txt"
        self.status.write_text("0\n")
        self.capture.joinpath("readback.rgba").write_bytes(m.payload())
        self.capture.joinpath("readback.receipt").write_text(RECEIPT)

    def run_collect(self):
        return m.collect(
            self.nro, self.sd, self.out, runner_log_path=self.log,
            exit_status_path=self.status, runtime="gpu_capable_emulator",
            command="FAKE UNIT TEST (NOT AN EXECUTION)")

    def test_new_session_has_exact_nonce_and_clears_old_capture(self):
        self.assertEqual(
            (self.capture/"run_nonce.txt").read_text(), CHALLENGE+"\n")
        self.assertEqual(self.session["state"], "prepared_not_executed")
        self.assertFalse(self.session["runtime_provenance_attested"])
        self.assertEqual(self.session["nro_sha256"], hashlib.sha256(FAKE_NRO).hexdigest())

    def test_fresh_prepare_clears_all_stage230_to_stage234_artifacts(self):
        stale_names = (
            "readback.rgba", "readback.receipt",
            "readback.rgba.tmp", "readback.receipt.tmp",
            "upload.rgba", "upload.rgba.tmp",
            "gpu_phase.txt", "gpu_phase.tmp",
            "guest_exit.txt", "guest_exit.tmp", "run_nonce.txt.tmp",
        )
        for name in stale_names:
            self.capture.joinpath(name).write_bytes(b"stale-private-test-data")
        fresh_out = self.out.parent / "fresh-owner-private"
        session = m.prepare(self.nro, self.sd, fresh_out, challenge=CHALLENGE)
        self.assertEqual(session["state"], "prepared_not_executed")
        for name in stale_names:
            with self.subTest(name=name):
                self.assertFalse(self.capture.joinpath(name).exists())
        self.assertEqual(
            self.capture.joinpath("run_nonce.txt").read_text(encoding="ascii"),
            CHALLENGE + "\n")

    def test_nonce_replacement_does_not_follow_preexisting_symlink(self):
        target = Path(self.temp.name) / "outside-target.txt"
        target.write_text("must remain unchanged", encoding="utf-8")
        nonce_path = self.capture / "run_nonce.txt"
        nonce_path.unlink(missing_ok=True)
        nonce_path.symlink_to(target)
        fresh_out = self.out.parent / "fresh-symlink-session"
        m.prepare(self.nro, self.sd, fresh_out, challenge=CHALLENGE)
        self.assertFalse(nonce_path.is_symlink())
        self.assertEqual(nonce_path.read_text(encoding="ascii"), CHALLENGE + "\n")
        self.assertEqual(target.read_text(encoding="utf-8"), "must remain unchanged")
        self.assertFalse((self.capture / "run_nonce.txt.tmp").exists())

    def test_synthetic_collection_does_not_attest_gpu(self):
        report = self.run_collect()
        self.assertEqual(report["result"], "submitted_capture_matches_challenge_and_pixels")
        self.assertFalse(report["runtime_provenance_attested"])
        self.assertEqual((self.out/"readback.rgba").read_bytes(), m.payload())
        with self.assertRaises(m.SessionError):
            self.run_collect()

    def test_stale_nonce_and_wrong_capture(self):
        self.capture.joinpath("readback.receipt").write_text(
            RECEIPT.replace(CHALLENGE, "f" * 32))
        with self.assertRaisesRegex(m.SessionError, "receipt nonce"):
            self.run_collect()
        self.capture.joinpath("readback.receipt").write_text(RECEIPT)
        self.capture.joinpath("run_nonce.txt").write_text("b" * 32 + "\n")
        with self.assertRaisesRegex(m.SessionError, "SD request"):
            self.run_collect()

    def test_pixel_corruption_and_failed_exit(self):
        wrong = bytearray(m.payload())
        wrong[39] ^= 1
        self.capture.joinpath("readback.rgba").write_bytes(wrong)
        with self.assertRaisesRegex(m.SessionError, "RGBA mismatch"):
            self.run_collect()
        self.capture.joinpath("readback.rgba").write_bytes(m.payload())
        self.status.write_text("1\n")
        with self.assertRaisesRegex(m.SessionError, "not zero"):
            self.run_collect()

    def test_malformed_receipt_and_missing_log(self):
        self.capture.joinpath("readback.receipt").write_text(RECEIPT.replace("mismatches=0", "mismatches=1"))
        with self.assertRaisesRegex(m.SessionError, "parameters"):
            self.run_collect()
        self.capture.joinpath("readback.receipt").write_text(RECEIPT)
        self.log.write_bytes(b"")
        with self.assertRaisesRegex(m.SessionError, "runner log"):
            self.run_collect()

    def test_preparation_rejects_reuse_and_invalid_nonce(self):
        with self.assertRaisesRegex(m.SessionError, "not empty"):
            m.prepare(self.nro, self.sd, self.out, challenge=CHALLENGE)
        with self.assertRaisesRegex(m.SessionError, "128-bit"):
            m.prepare(self.nro, self.sd, self.out / "new", challenge="f" * 31 + "Z")

    def test_missing_gpu_sd_files_fail_closed(self):
        self.capture.joinpath("readback.receipt").unlink()
        with self.assertRaisesRegex(m.SessionError, "completion receipt"):
            self.run_collect()
        self.capture.joinpath("readback.receipt").write_text(RECEIPT)
        self.capture.joinpath("readback.rgba").write_bytes(b"xyz")
        with self.assertRaisesRegex(m.SessionError, "sized GPU"):
            self.run_collect()

    def test_nonce_is_not_gpu_proof_even_with_forged_metadata(self):
        report = m.validate(self.session, CHALLENGE+"\n", m.payload(), RECEIPT,
                            hashlib.sha256(FAKE_NRO).hexdigest(), 0,
                            b"mock backend calls", "gpu_capable_emulator",
                            "invented-launcher")
        self.assertFalse(report["runtime_provenance_attested"])

    def test_bad_nro_after_prepare(self):
        self.nro.write_bytes(FAKE_NRO + b"x")
        with self.assertRaisesRegex(m.SessionError, "different NRO"):
            self.run_collect()

    def test_bad_request_rejects_rerun(self):
        self.capture.joinpath("run_nonce.txt").write_text(CHALLENGE)
        with self.assertRaisesRegex(m.SessionError, "SD request"):
            self.run_collect()


if __name__ == "__main__":
    unittest.main()
