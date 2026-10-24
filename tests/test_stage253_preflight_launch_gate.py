"""Stage253 gate tests bind a preflight to exact launch inputs without running them."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage252_runtime_preflight as preflight
import stage253_preflight_launch_gate as gate


class Stage253PreflightLaunchGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.emulator = self.root / "synthetic-emulator"
        self.emulator.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        self.emulator.chmod(0o700)
        self.nro = self.root / "synthetic.nro"
        self.nro.write_bytes(bytes(16) + b"NRO0" + b"synthetic-fixture")
        self.sd_root = self.root / "sd"
        self.sd_root.mkdir()
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        if os.name != "nt":
            self.private.chmod(0o700)
        self.session = self.private / "session"
        self.report_path = self.private / "stage252.json"
        self.args = ["--no-gui", "{nro}"]

    def make_report(self, *, mapping_confirmed=True):
        return preflight.preflight(
            self.emulator,
            self.nro,
            self.sd_root,
            self.session,
            self.args,
            sd_root_mapping_confirmed=mapping_confirmed,
        )

    def save_report(self, report):
        preflight.write_report(
            self.report_path,
            json.dumps(report, sort_keys=True, indent=2) + "\n",
        )

    def validate(self, **kwargs):
        return gate.validate_preflight_report(
            self.report_path,
            self.emulator,
            self.nro,
            self.sd_root,
            self.session,
            self.args,
            **kwargs,
        )

    def test_recent_matching_report_is_accepted_without_gpu_attestation(self):
        self.save_report(self.make_report())
        result = self.validate()
        self.assertTrue(result["accepted"])
        self.assertEqual(result["schema"], "heman-stage253-preflight-launch-gate-v1")
        self.assertTrue(result["path_fingerprints_matched"])
        self.assertTrue(result["launch_argument_fingerprint_matched"])
        self.assertTrue(result["sd_root_mapping_operator_confirmed"])
        self.assertFalse(result["sd_root_mapping_independently_verified"])
        self.assertFalse(result["runtime_gpu_execution_attested"])
        self.assertFalse(result["original_ios_graphics_parity_attested"])
        self.assertEqual(len(result["stage252_report_sha256"]), 64)

    def test_blocked_preflight_cannot_open_gate(self):
        self.save_report(self.make_report(mapping_confirmed=False))
        with self.assertRaisesRegex(gate.PreflightGateError, "did not pass"):
            self.validate()

    def test_changed_argument_template_is_rejected(self):
        self.save_report(self.make_report())
        with self.assertRaisesRegex(gate.PreflightGateError, "fingerprint mismatch"):
            gate.validate_preflight_report(
                self.report_path,
                self.emulator,
                self.nro,
                self.sd_root,
                self.session,
                ["--windowed", "{nro}"],
            )

    def test_changed_nro_bytes_are_rejected(self):
        self.save_report(self.make_report())
        self.nro.write_bytes(bytes(16) + b"NRO0" + b"changed-fixture")
        with self.assertRaisesRegex(gate.PreflightGateError, "NRO file changed"):
            self.validate()

    def test_changed_emulator_bytes_are_rejected(self):
        self.save_report(self.make_report())
        self.emulator.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.emulator.chmod(0o700)
        with self.assertRaisesRegex(gate.PreflightGateError, "emulator file changed"):
            self.validate()

    def test_stale_report_is_rejected(self):
        report = self.make_report()
        report["created_utc"] = (
            datetime.now(timezone.utc) - timedelta(seconds=gate.DEFAULT_MAX_AGE_SECONDS + 10)
        ).isoformat()
        self.save_report(report)
        with self.assertRaisesRegex(gate.PreflightGateError, "stale"):
            self.validate()

    def test_modified_attestation_field_is_rejected(self):
        report = self.make_report()
        report["runtime_gpu_execution_attested"] = True
        self.save_report(report)
        with self.assertRaisesRegex(gate.PreflightGateError, "unexpected evidence claim"):
            self.validate()

    def test_missing_path_fingerprint_is_rejected(self):
        report = self.make_report()
        del report["path_fingerprints"]["sd_root_path_sha256"]
        self.save_report(report)
        with self.assertRaisesRegex(gate.PreflightGateError, "fingerprint mismatch"):
            self.validate()

    def test_oversized_report_is_rejected(self):
        self.report_path.write_bytes(b"x" * (gate.MAX_REPORT_BYTES + 1))
        with self.assertRaisesRegex(gate.PreflightGateError, "exceeds"):
            self.validate()

    def test_symlink_report_is_rejected(self):
        target = self.private / "target.json"
        target.write_text("{}", encoding="utf-8")
        try:
            self.report_path.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        with self.assertRaisesRegex(gate.PreflightGateError, "non-symlink"):
            self.validate()

    def test_report_inside_sd_root_is_rejected(self):
        report = self.make_report()
        inside = self.sd_root / "preflight.json"
        inside.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(gate.PreflightGateError, "inside the SD root"):
            gate.validate_preflight_report(
                inside, self.emulator, self.nro, self.sd_root, self.session, self.args
            )

    def test_symlinked_stage230_path_added_after_preflight_is_rejected(self):
        self.save_report(self.make_report())
        external = self.root / "external"
        external.mkdir()
        link = self.sd_root / "switch"
        try:
            link.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        with self.assertRaisesRegex(gate.PreflightGateError, "path components"):
            self.validate()

    def test_session_that_became_nonempty_is_rejected(self):
        self.save_report(self.make_report())
        self.session.mkdir()
        (self.session / "stale.txt").write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(gate.PreflightGateError, "no longer empty"):
            self.validate()

    def test_future_timestamp_is_rejected(self):
        report = self.make_report()
        report["created_utc"] = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
        self.save_report(report)
        with self.assertRaisesRegex(gate.PreflightGateError, "future"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
