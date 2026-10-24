from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import stage257_private_host_evidence_archive as m


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Stage257PrivateArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="heman-stage257-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        if os.name != "nt":
            self.private.chmod(0o700)
        self.session = self.private / "session"
        self.session.mkdir(mode=0o700)
        if os.name != "nt":
            self.session.chmod(0o700)
        self.sd_root = self.root / "sd-root"
        self.capture = self.sd_root / "switch" / "heman-stage230"
        self.capture.mkdir(parents=True)
        self.report_path = self.private / "stage252_preflight.json"
        self.output_path = self.private / "host-evidence.zip"
        self.challenge = "a" * 32
        self.payload = bytes(range(256)) * 2
        self.receipt = b"synthetic receipt\n"
        emulator = b"synthetic emulator bytes"
        nro = bytearray(32)
        nro[16:20] = b"NRO0"
        nro = bytes(nro)
        emulator_hash = digest(emulator)
        nro_hash = digest(nro)
        self.preflight = {
            "schema": "heman-stage252-runtime-preflight-v1",
            "result": "preflight_passed_not_launched",
            "checks": {
                "all_input_paths_absolute": True,
                "emulator_regular_non_symlink": True,
                "emulator_executable": True,
                "nro_regular_non_symlink": True,
                "nro_size_in_range": True,
                "nro0_header_valid": True,
                "sd_root_existing_non_symlink_directory": True,
                "sd_root_writable": True,
                "sd_capture_directory_chain_safe": True,
                "sd_root_mapping_operator_confirmed": True,
                "session_target_fresh_and_private": True,
                "input_and_output_paths_separated": True,
                "launch_argument_template_valid": True,
            },
            "sha256": {"emulator_sha256": emulator_hash, "nro_sha256": nro_hash},
            "sd_root_mapping_independently_verified": False,
            "emulator_was_launched": False,
            "runtime_gpu_execution_attested": False,
            "gpu_capability_independently_verified": False,
            "original_ios_graphics_parity_attested": False,
        }
        self.preflight_raw = json_bytes(self.preflight)
        self.report_path.write_bytes(self.preflight_raw)
        gate = {
            "accepted": True,
            "stage252_report_sha256": digest(self.preflight_raw),
            "stage252_report_age_seconds": 4,
            "emulator_sha256": emulator_hash,
            "nro_sha256": nro_hash,
        }
        self.launch = {
            "schema": "stage240-host-emulator-attempt-v1",
            "prepared_session_nonce": self.challenge,
            "nro_sha256": nro_hash,
            "emulator_executable_sha256": emulator_hash,
            "stage252_preflight_gate_status": "accepted",
            "stage252_preflight_gate": gate,
            "test_only_runner_declared": False,
            "runtime_gpu_execution_attested": False,
            "emulator_gpu_capability_independently_verified": False,
            "guest_process_exit_independently_verified": False,
            "host_process_exit_code": 0,
            "host_timed_out": False,
            "stage231_collected": True,
            "stage236_bundle_consistent": True,
            "stage241_guest_exit_receipt_accepted": True,
            "runtime_backend_log_audit_status": "complete",
        }
        self.session_manifest = {
            "schema": "stage231-capture-session-v1",
            "state": "prepared_not_executed",
            "nonce": self.challenge,
            "nro_sha256": nro_hash,
            "runtime_provenance_attested": False,
        }
        self.collected = {
            "schema": "stage231-collected-synthetic-gpu-evidence-v1",
            "result": "submitted_capture_matches_challenge_and_pixels",
            "nonce": self.challenge,
            "rgba_sha256": digest(self.payload),
            "runtime_provenance_attested": False,
            "warning": "Synthetic test fixture; does not prove GPU execution.",
        }
        (self.session / "stage240_launch.json").write_bytes(json_bytes(self.launch))
        (self.session / "stage231_session.json").write_bytes(json_bytes(self.session_manifest))
        (self.session / "stage231_collected.json").write_bytes(json_bytes(self.collected))
        (self.session / "stage240_bundle.json").write_bytes(json_bytes({"synthetic_bundle_consistent": True}))
        (self.session / "host-launch.log").write_bytes(b"synthetic host log\n")
        (self.session / "runner-exit-status.txt").write_bytes(b"0\n")
        (self.session / "readback.rgba").write_bytes(self.payload)
        (self.session / "readback.receipt").write_bytes(self.receipt)
        (self.session / "runtime.log").write_bytes(b"synthetic runtime log\n")
        (self.session / "exit-status.txt").write_bytes(b"0\n")
        (self.capture / "run_nonce.txt").write_bytes((self.challenge + "\n").encode("ascii"))
        (self.capture / "readback.rgba").write_bytes(self.payload)
        (self.capture / "readback.receipt").write_bytes(self.receipt)
        (self.capture / "guest_exit.txt").write_bytes(b"synthetic guest receipt\n")
        (self.capture / "gpu_phase.txt").write_bytes(b"synthetic phase marker\n")

    def test_valid_archive_contains_whitelisted_evidence_and_hashes(self):
        result = m.archive_host_evidence(
            self.report_path, self.session, self.sd_root, self.output_path
        )
        self.assertTrue(self.output_path.is_file())
        self.assertEqual(result["archive_sha256"], digest(self.output_path.read_bytes()))
        self.assertFalse(result["runtime_gpu_execution_attested"])
        self.assertFalse(result["gpu_capability_independently_verified"])
        with zipfile.ZipFile(self.output_path) as archive:
            names = set(archive.namelist())
            self.assertIn("stage252_preflight.json", names)
            self.assertIn("session/stage240_launch.json", names)
            self.assertIn("session/stage231_session.json", names)
            self.assertIn("session/stage231_collected.json", names)
            self.assertIn("sd_capture/readback.rgba", names)
            self.assertNotIn("emulator", names)
            self.assertNotIn("nro", names)
            manifest = json.loads(archive.read("stage257_archive_manifest.json"))
            self.assertFalse(manifest["runtime_gpu_execution_attested"])
            self.assertFalse(manifest["original_emulator_and_nro_binaries_included"])
            self.assertTrue(all(not Path(entry["name"]).is_absolute() for entry in manifest["included_files"]))
            record = next(item for item in manifest["included_files"] if item["name"] == "session/readback.rgba")
            self.assertEqual(record["sha256"], digest(self.payload))
        if os.name != "nt":
            self.assertEqual(self.output_path.stat().st_mode & 0o777, 0o600)

    def test_rejects_changed_preflight_report_hash(self):
        self.report_path.write_bytes(json_bytes({**self.preflight, "note": "changed after launch"}))
        with self.assertRaisesRegex(m.ArchiveError, "report hash does not match"):
            m.archive_host_evidence(self.report_path, self.session, self.sd_root, self.output_path)
        self.assertFalse(self.output_path.exists())

    def test_rejects_test_only_runner_manifest(self):
        self.launch["test_only_runner_declared"] = True
        (self.session / "stage240_launch.json").write_bytes(json_bytes(self.launch))
        with self.assertRaisesRegex(m.ArchiveError, "test-only runner"):
            m.archive_host_evidence(self.report_path, self.session, self.sd_root, self.output_path)
        self.assertFalse(self.output_path.exists())

    def test_rejects_symlinked_capture_file(self):
        target = self.root / "outside-capture.bin"
        target.write_bytes(self.payload)
        capture_file = self.capture / "readback.rgba"
        capture_file.unlink()
        try:
            capture_file.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable on this host")
        with self.assertRaisesRegex(m.ArchiveError, "regular non-symlink file"):
            m.archive_host_evidence(self.report_path, self.session, self.sd_root, self.output_path)
        self.assertFalse(self.output_path.exists())
        self.assertEqual(target.read_bytes(), self.payload)

    def test_refuses_archive_inside_session_directory(self):
        output = self.session / "archive.zip"
        with self.assertRaisesRegex(m.ArchiveError, "outside session and SD"):
            m.archive_host_evidence(self.report_path, self.session, self.sd_root, output)
        self.assertFalse(output.exists())

    def test_refuses_public_report_directory_on_posix(self):
        if os.name == "nt":
            self.skipTest("POSIX mode bits do not describe Windows ACL privacy")
        public = self.root / "public-report"
        public.mkdir(mode=0o755)
        public.chmod(0o755)
        report = public / "stage252.json"
        report.write_bytes(self.preflight_raw)
        with self.assertRaisesRegex(m.ArchiveError, "owner-private"):
            m.archive_host_evidence(report, self.session, self.sd_root, self.output_path)
        self.assertFalse(self.output_path.exists())


if __name__ == "__main__":
    unittest.main()
