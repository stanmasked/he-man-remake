"""Stage252 read-only runtime preflight tests; no emulator is ever launched."""
from pathlib import Path
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage252_runtime_preflight as m


class Stage252RuntimePreflightTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.emulator = self.root / "synthetic-emulator"
        self.emulator.write_text(
            "#!/bin/sh\n# synthetic executable; preflight must not run this\nexit 99\n",
            encoding="utf-8",
        )
        self.emulator.chmod(0o700)
        self.nro = self.root / "synthetic-probe.nro"
        self.nro.write_bytes(bytes(16) + b"NRO0" + b"synthetic-fixture")
        self.sd_root = self.root / "sd"
        self.sd_root.mkdir()
        self.private_parent = self.root / "private"
        self.private_parent.mkdir(mode=0o700)
        if os.name != "nt":
            self.private_parent.chmod(0o700)
        self.session = self.private_parent / "session"
        self.marker = self.root / "emulator-was-run.marker"

    def run_preflight(self, **overrides):
        values = {
            "emulator": self.emulator,
            "nro": self.nro,
            "sd_root": self.sd_root,
            "session_dir": self.session,
            "launch_args": ["--no-gui", "{nro}"],
            "sd_root_mapping_confirmed": True,
        }
        values.update(overrides)
        return m.preflight(**values)

    def test_valid_synthetic_paths_pass_but_never_attest_gpu_or_launch(self):
        # If invoked, this script would create a marker. The preflight must not run it.
        self.emulator.write_text(
            f"#!/bin/sh\ntouch '{self.marker}'\nexit 0\n", encoding="utf-8"
        )
        self.emulator.chmod(0o700)
        report = self.run_preflight()
        self.assertEqual(report["result"], "preflight_passed_not_launched")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(len(report["sha256"]["emulator_sha256"]), 64)
        self.assertEqual(len(report["sha256"]["nro_sha256"]), 64)
        self.assertFalse(self.marker.exists())
        self.assertFalse(report["emulator_was_launched"])
        self.assertFalse(report["runtime_gpu_execution_attested"])
        self.assertFalse(report["gpu_capability_independently_verified"])
        self.assertFalse(report["original_ios_graphics_parity_attested"])
        self.assertFalse(report["sd_root_mapping_independently_verified"])

    def test_missing_mapping_confirmation_blocks_readiness(self):
        report = self.run_preflight(sd_root_mapping_confirmed=False)
        self.assertEqual(report["result"], "preflight_blocked")
        self.assertFalse(report["checks"]["sd_root_mapping_operator_confirmed"])
        self.assertFalse(report["sd_root_mapping_independently_verified"])

    def test_invalid_nro_magic_blocks_readiness(self):
        self.nro.write_bytes(bytes(16) + b"NOPE" + b"fixture")
        report = self.run_preflight()
        self.assertFalse(report["checks"]["nro0_header_valid"])
        self.assertEqual(report["result"], "preflight_blocked")

    def test_oversized_nro_is_rejected_before_hashing(self):
        with self.nro.open("wb") as stream:
            stream.truncate(m.MAX_NRO_BYTES + 1)
        report = self.run_preflight()
        self.assertFalse(report["checks"]["nro_size_in_range"])
        self.assertIsNone(report["sha256"]["nro_sha256"])

    def test_symlinked_emulator_is_rejected(self):
        link = self.root / "emulator-link"
        try:
            link.symlink_to(self.emulator)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        report = self.run_preflight(emulator=link)
        self.assertFalse(report["checks"]["emulator_regular_non_symlink"])
        self.assertEqual(report["result"], "preflight_blocked")

    def test_symlinked_stage230_directory_chain_is_rejected(self):
        external = self.root / "external-sd-output"
        external.mkdir()
        link = self.sd_root / "switch"
        try:
            link.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        report = self.run_preflight()
        self.assertFalse(report["checks"]["sd_capture_directory_chain_safe"])
        self.assertEqual(report["result"], "preflight_blocked")

    def test_symlinked_sd_root_is_rejected(self):
        link = self.root / "sd-link"
        try:
            link.symlink_to(self.sd_root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        report = self.run_preflight(sd_root=link)
        self.assertFalse(report["checks"]["sd_root_existing_non_symlink_directory"])
        self.assertEqual(report["result"], "preflight_blocked")

    def test_nonempty_session_is_rejected(self):
        self.session.mkdir()
        (self.session / "stale.json").write_text("stale", encoding="utf-8")
        report = self.run_preflight()
        self.assertFalse(report["checks"]["session_target_fresh_and_private"])
        self.assertEqual(report["result"], "preflight_blocked")

    def test_session_inside_sd_root_is_rejected(self):
        report = self.run_preflight(session_dir=self.sd_root / "session")
        self.assertFalse(report["checks"]["input_and_output_paths_separated"])
        self.assertEqual(report["result"], "preflight_blocked")

    def test_nro_placeholder_must_be_exactly_once_and_standalone(self):
        for args in ([], ["{nro}", "{nro}"], ["--file={nro}"]):
            with self.subTest(args=args):
                report = self.run_preflight(launch_args=args)
                self.assertFalse(report["checks"]["launch_argument_template_valid"])
                self.assertEqual(report["result"], "preflight_blocked")

    def test_relative_input_path_is_blocked(self):
        report = self.run_preflight(nro=Path("relative-probe.nro"))
        self.assertFalse(report["checks"]["all_input_paths_absolute"])
        self.assertEqual(report["result"], "preflight_blocked")

    def test_output_report_refuses_to_overwrite_existing_evidence(self):
        report = self.private_parent / "prior-report.json"
        report.write_text("preserve-me", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            m.write_report(report, '{"new": true}\\n')
        self.assertEqual(report.read_text(encoding="utf-8"), "preserve-me")

    def test_output_report_requires_private_posix_parent_by_default(self):
        if os.name == "nt":
            self.skipTest("Windows ACLs are not audited by the Python standard library")
        public_parent = self.root / "public-output"
        public_parent.mkdir(mode=0o755)
        public_parent.chmod(0o755)
        report = public_parent / "synthetic.json"
        with self.assertRaisesRegex(ValueError, "owner-private"):
            m.write_report(report, '{"synthetic": true}\\n')
        m.write_report(
            report,
            '{"synthetic": true}\\n',
            allow_public_output_for_synthetic_ci=True,
        )
        self.assertEqual(report.read_text(encoding="utf-8"), '{"synthetic": true}\\n')
        self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_symlink_output_report_is_rejected(self):
        target = self.private_parent / "target.json"
        target.write_text("target", encoding="utf-8")
        link = self.private_parent / "report-link.json"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        with self.assertRaisesRegex(ValueError, "symlink"):
            m.write_report(link, '{"x": 1}\\n')
        self.assertEqual(target.read_text(encoding="utf-8"), "target")

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not Windows ACLs")
    def test_publicly_accessible_session_parent_is_rejected(self):
        self.private_parent.chmod(0o755)
        report = self.run_preflight()
        self.assertFalse(report["checks"]["session_target_fresh_and_private"])
        self.assertEqual(report["result"], "preflight_blocked")


if __name__ == "__main__":
    unittest.main()
