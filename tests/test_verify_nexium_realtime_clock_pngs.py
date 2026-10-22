"""Stage184: fail-closed tests for the synthetic guest OCR verifier."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from tools import verify_nexium_realtime_clock_pngs as verifier


class RealtimeClockPngVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def capture(self, index, size=(640, 360), image_format="PNG", visible=True):
        image = Image.new("RGB", size, "black")
        if visible:
            ImageDraw.Draw(image).rectangle((5, 5, 40, 40), fill="white")
        path = self.folder / f"raster-frame-{index:04}.png"
        image.save(path, format=image_format)
        return path

    def all_captures(self, **kwargs):
        for index in verifier.FRAME_INDICES:
            self.capture(index, **kwargs)

    @staticmethod
    def ocr_result(text):
        return SimpleNamespace(returncode=0, stdout=text, stderr="")

    def mock_ocr_by_frame(self, mapping):
        def run(args, **kwargs):
            name = Path(args[1]).name
            index = int(name.split("-")[2])
            return self.ocr_result(mapping[index])

        return run

    def test_success_requires_pass_marker_on_a_late_frame(self):
        self.all_captures()
        with patch.object(verifier.subprocess, "run", side_effect=self.mock_ocr_by_frame({
            30: "STARTUP COUNTER RESUME PASS",
            120: "STARTUP COUNTER RESUME",
            300: "Startup counter pause resume self-check: PASS",
        })):
            report = verifier.verify(self.folder)
        self.assertEqual(report["captured_frames"], [30, 120, 300])
        self.assertEqual(report["pass_marker_frames"], [300])

    def test_pass_marker_with_fail_token_is_rejected(self):
        self.assertFalse(verifier.has_pass_marker("STARTUP COUNTER RESUME PASS FAIL"))

    def test_missing_late_pass_marker_fails_closed(self):
        self.all_captures()
        with patch.object(
            verifier.subprocess, "run",
            return_value=self.ocr_result("STARTUP COUNTER RESUME"),
        ):
            with self.assertRaisesRegex(ValueError, "No late guest frame OCR"):
                verifier.verify(self.folder)

    def test_missing_capture_fails_closed(self):
        self.capture(30)
        self.capture(300)
        with patch.object(
            verifier.subprocess, "run",
            return_value=self.ocr_result("STARTUP COUNTER RESUME PASS"),
        ):
            with self.assertRaisesRegex(FileNotFoundError, "frame 120"):
                verifier.verify(self.folder)

    def test_unsupported_frame_dimensions_fail_closed(self):
        self.capture(30, size=(800, 450))
        with patch.object(verifier.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Unexpected guest frame 30 dimensions"):
                verifier.verify(self.folder)
        run.assert_not_called()

    def test_too_little_visible_guest_output_fails(self):
        self.all_captures(visible=False)
        with patch.object(
            verifier.subprocess, "run",
            return_value=self.ocr_result("STARTUP COUNTER RESUME PASS"),
        ):
            with self.assertRaisesRegex(ValueError, "too little visible console output"):
                verifier.verify(self.folder)

    def test_tesseract_failure_is_reported(self):
        path = self.capture(30)
        with TemporaryDirectory() as scratch, patch.object(
            verifier.subprocess, "run",
            return_value=SimpleNamespace(returncode=1, stdout="", stderr="ocr failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Tesseract failed for frame 30: ocr failed"):
                verifier.read_and_ocr(path, Path(scratch), 30)

    def test_non_png_file_is_rejected_even_when_named_png(self):
        path = self.capture(30, image_format="JPEG")
        with TemporaryDirectory() as scratch, patch.object(verifier.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "is not PNG"):
                verifier.read_and_ocr(path, Path(scratch), 30)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
