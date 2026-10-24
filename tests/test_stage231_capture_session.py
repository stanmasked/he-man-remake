"""Stage231 anti-replay regressions. Entirely invented data, not GPU evidence."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))

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

    def test_prepare_rejects_symlinked_switch_directory(self):
        root = self.sd.parent
        sd_root = root / "symlinked-switch-sd"
        sd_root.mkdir()
        external = root / "external-switch-target"
        external.mkdir()
        try:
            (sd_root / "switch").symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        fresh_out = root / "new-owner-private-switch-test"
        with self.assertRaisesRegex(m.SessionError, "non-symlink directories"):
            m.prepare(self.nro, sd_root, fresh_out, challenge=CHALLENGE)
        self.assertFalse((external / "heman-stage230").exists())
        self.assertFalse((fresh_out / "stage231_session.json").exists())

    def test_prepare_rejects_symlinked_heman_stage230_directory(self):
        root = self.sd.parent
        sd_root = root / "symlinked-stage230-sd"
        switch = sd_root / "switch"
        switch.mkdir(parents=True)
        external = root / "external-stage230-target"
        external.mkdir()
        try:
            (switch / "heman-stage230").symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        fresh_out = root / "new-owner-private-stage230-test"
        with self.assertRaisesRegex(m.SessionError, "non-symlink directories"):
            m.prepare(self.nro, sd_root, fresh_out, challenge=CHALLENGE)
        self.assertFalse((external / "run_nonce.txt").exists())
        self.assertFalse((fresh_out / "stage231_session.json").exists())

    def test_prepare_uses_pinned_capture_directory_after_switch_path_replacement(self):
        if not m._supports_descriptor_io():
            self.skipTest("descriptor-relative capture I/O is unsupported")
        root = self.sd.parent
        sd_root = root / "pinned-prepare-sd"
        output = root / "pinned-prepare-output"
        external = root / "replacement-switch-target"
        external.mkdir()
        probe = root / "symlink-probe"
        try:
            probe.symlink_to(external, target_is_directory=True)
            probe.unlink()
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        original_open = m._open_sd_capture_dir_fd
        def open_then_replace(path, *, create):
            fd = original_open(path, create=create)
            if path == sd_root:
                (sd_root / "switch").rename(sd_root / "switch-original")
                (sd_root / "switch").symlink_to(external, target_is_directory=True)
            return fd
        with mock.patch.object(m, "_open_sd_capture_dir_fd", side_effect=open_then_replace):
            m.prepare(self.nro, sd_root, output, challenge=CHALLENGE)
        pinned_capture = sd_root / "switch-original" / "heman-stage230"
        self.assertEqual((pinned_capture / "run_nonce.txt").read_text(), CHALLENGE + "\n")
        self.assertFalse((external / "run_nonce.txt").exists())
        self.assertTrue((output / "stage231_session.json").is_file())

    def test_collect_reads_pinned_capture_after_switch_path_replacement(self):
        if not m._supports_descriptor_io():
            self.skipTest("descriptor-relative capture I/O is unsupported")
        root = self.sd.parent
        external = root / "replacement-collect-target"
        external.mkdir()
        (external / "heman-stage230").mkdir()
        (external / "heman-stage230" / "run_nonce.txt").write_text("f" * 32 + "\n")
        (external / "heman-stage230" / "readback.rgba").write_bytes(b"X" * 512)
        (external / "heman-stage230" / "readback.receipt").write_text("decoy receipt")
        probe = root / "collect-symlink-probe"
        try:
            probe.symlink_to(external, target_is_directory=True)
            probe.unlink()
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        original_open = m._open_sd_capture_dir_fd
        def open_then_replace(path, *, create):
            fd = original_open(path, create=create)
            if path == self.sd and not create:
                (self.sd / "switch").rename(self.sd / "switch-original")
                (self.sd / "switch").symlink_to(external, target_is_directory=True)
            return fd
        with mock.patch.object(m, "_open_sd_capture_dir_fd", side_effect=open_then_replace):
            result = self.run_collect()
        self.assertEqual(result["rgba_sha256"], hashlib.sha256(m.payload()).hexdigest())
        self.assertEqual((self.out / "readback.rgba").read_bytes(), m.payload())
        self.assertEqual((external / "heman-stage230" / "readback.rgba").read_bytes(), b"X" * 512)

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


    def test_oversized_raw_log_is_rejected_without_collection(self):
        with self.log.open("wb") as stream:
            stream.truncate(4*1024*1024+1)
        with self.assertRaisesRegex(m.SessionError,"runner log.*oversized"):
            self.run_collect()
        self.assertFalse((self.out/"stage231_collected.json").exists())

    def test_oversized_receipt_and_nonce_are_rejected(self):
        self.capture.joinpath("readback.receipt").write_bytes(b"x"*257)
        with self.assertRaisesRegex(m.SessionError,"completion receipt.*oversized"):
            self.run_collect()
        self.capture.joinpath("readback.receipt").write_text(RECEIPT)
        self.capture.joinpath("run_nonce.txt").write_bytes(b"n"*65)
        with self.assertRaisesRegex(m.SessionError,"SD request nonce.*oversized"):
            self.run_collect()

    def test_oversized_prepared_manifest_and_exit_status(self):
        self.out.joinpath("stage231_session.json").write_bytes(b"x"*(64*1024+1))
        with self.assertRaisesRegex(m.SessionError,"prepared session manifest.*oversized"):
            self.run_collect()
        import json
        self.out.joinpath("stage231_session.json").write_text(
            json.dumps(self.session),encoding="utf-8")
        self.status.write_bytes(b"0"*65)
        with self.assertRaisesRegex(m.SessionError,"exit status.*oversized"):
            self.run_collect()

    def test_nonce_is_not_gpu_proof_even_with_forged_metadata(self):
        report = m.validate(self.session, CHALLENGE+"\n", m.payload(), RECEIPT,
                            hashlib.sha256(FAKE_NRO).hexdigest(), 0,
                            b"mock backend calls", "gpu_capable_emulator",
                            "invented-launcher")
        self.assertFalse(report["runtime_provenance_attested"])

    def test_nro_hash_rejects_symlink_to_valid_nro(self):
        if not getattr(__import__("os"), "O_NOFOLLOW", 0):
            self.skipTest("O_NOFOLLOW is unsupported")
        link = self.sd.parent / "nro-symlink"
        try:
            link.symlink_to(self.nro)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        with self.assertRaisesRegex(m.SessionError, "non-symlink file"):
            m.nro_sha256(link)

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
