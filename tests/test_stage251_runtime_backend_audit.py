"""Stage251 log classification tests; synthetic logs are not GPU evidence."""
from pathlib import Path
import os
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage251_runtime_backend_audit as audit


class Stage251RuntimeBackendAuditTests(unittest.TestCase):
    def test_single_api_without_software_marker_is_only_a_log_claim(self):
        report = audit.analyze_bytes(
            b"startup complete\nGPU Backend: Vulkan\nRenderer: Example Adapter\n",
            "synthetic.log",
        )
        self.assertEqual(report["classification"],
                         "graphics_api_reported_no_software_marker")
        self.assertEqual(report["reported_backends"], ["vulkan"])
        self.assertEqual(report["backend_evidence_line_numbers"]["vulkan"], [2])
        self.assertTrue(report["api_reported_without_software_marker"])
        self.assertFalse(report["gpu_capability_independently_verified"])
        self.assertFalse(report["runtime_gpu_execution_attested"])
        self.assertFalse(report["original_ios_graphics_parity_attested"])

    def test_software_renderer_marker_overrides_graphics_api_claim(self):
        report = audit.analyze_bytes(
            b"GPU Backend: Vulkan\nRenderer: llvmpipe (LLVM 18.0)\n"
        )
        self.assertEqual(report["classification"],
                         "software_rendering_indicator_found")
        self.assertEqual(report["reported_backends"], ["vulkan"])
        self.assertIn("llvmpipe", report["software_indicators"])
        self.assertFalse(report["api_reported_without_software_marker"])

    def test_explicit_software_backend_is_detected(self):
        report = audit.analyze_bytes(b"Graphics Backend: Software\n")
        self.assertEqual(report["classification"],
                         "software_rendering_indicator_found")
        self.assertIn("software_backend", report["software_indicators"])

    def test_multiple_graphics_apis_are_ambiguous(self):
        report = audit.analyze_bytes(
            b"GPU Backend: Vulkan\nGraphics API: OpenGL\n"
        )
        self.assertEqual(report["classification"],
                         "multiple_or_conflicting_graphics_apis")
        self.assertEqual(report["reported_backends"], ["vulkan", "opengl"])
        self.assertFalse(report["api_reported_without_software_marker"])

    def test_missing_backend_evidence_is_not_inferred(self):
        report = audit.analyze_bytes(b"emulator booted successfully\n")
        self.assertEqual(report["classification"],
                         "no_recognized_backend_evidence")
        self.assertEqual(report["reported_backends"], [])
        self.assertFalse(report["api_reported_without_software_marker"])

    def test_log_hash_and_size_are_deterministic(self):
        data = b"GPU Backend: OpenGL\n"
        report = audit.analyze_bytes(data, "runtime.log")
        import hashlib
        self.assertEqual(report["log_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(report["log_bytes"], len(data))
        self.assertEqual(report["source_name"], "runtime.log")

    def test_maximum_size_is_accepted_and_oversize_is_rejected(self):
        accepted = audit.analyze_bytes(b"x" * audit.MAX_LOG_BYTES)
        self.assertEqual(accepted["log_bytes"], audit.MAX_LOG_BYTES)
        with self.assertRaisesRegex(audit.AuditError, "exceeds"):
            audit.analyze_bytes(b"x" * (audit.MAX_LOG_BYTES + 1))

    def test_file_requires_absolute_regular_non_symlink_path(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            log = folder / "runtime.log"
            log.write_bytes(b"GPU Backend: Vulkan\n")
            self.assertEqual(
                audit.analyze_file(log)["classification"],
                "graphics_api_reported_no_software_marker",
            )
            with self.assertRaisesRegex(audit.AuditError, "absolute"):
                audit.analyze_file(Path("relative.log"))
            link = folder / "runtime-link.log"
            try:
                link.symlink_to(log)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable on this host")
            with self.assertRaisesRegex(audit.AuditError, "symbolic link"):
                audit.analyze_file(link)

    def test_oversized_file_is_rejected_before_reading(self):
        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / "runtime.log"
            with log.open("wb") as stream:
                stream.truncate(audit.MAX_LOG_BYTES + 1)
            with self.assertRaisesRegex(audit.AuditError, "exceeds"):
                audit.analyze_file(log)


if __name__ == "__main__":
    unittest.main()
