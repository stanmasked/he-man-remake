"""Regressions for the strict real-time guest OCR gate."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_nexium_realtime_clock_pngs import has_pass_marker, normalize


class RealtimeClockOcrGateTests(unittest.TestCase):
    def test_exact_ordered_self_check_phrase_passes(self):
        self.assertTrue(has_pass_marker(
            "Startup real-counter pause/resume self-check: PASS"
        ))

    def test_observed_contextual_tesseract_misread_passes(self):
        # Actual NeXium OCR misread RESUME as SRASUNE and FOR as FPR.
        self.assertTrue(has_pass_marker(
            "SCHEDULER UPDATES STARTUP REAL COUNTER PAUSE SRASUNE "
            "SELF CHECK PASS FPR GATE RESUMES 66 95 AND 66 MS CAP"
        ))

    def test_trailing_gate_resumes_label_alone_does_not_satisfy_phrase(self):
        self.assertFalse(has_pass_marker(
            "STARTUP REAL COUNTER PAUSE SELF CHECK PASS FOR GATE RESUMES"
        ))

    def test_resume_pass_without_self_check_is_rejected(self):
        self.assertFalse(has_pass_marker("STARTUP COUNTER RESUME PASS"))

    def test_unordered_resume_token_is_rejected(self):
        self.assertFalse(has_pass_marker(
            "STARTUP COUNTER SELF CHECK PASS PAUSE RESUME"
        ))

    def test_fail_token_anywhere_rejects_otherwise_valid_phrase(self):
        self.assertFalse(has_pass_marker(
            "STARTUP COUNTER PAUSE RESUME SELF CHECK PASS FAIL"
        ))

    def test_normalization_retains_the_observed_ocr_token(self):
        self.assertIn("SRASUNE", normalize("pause/SRASUNE self-check"))


if __name__ == "__main__":
    unittest.main()
