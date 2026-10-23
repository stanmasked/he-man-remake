"""Stage225 synthetic fixture tests: reject false NeXium padded PNG proofs."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageDraw

from tools import verify_nexium_png_padding_guest as verifier


class PaddedPNGGuestVerifierTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)

    def _capture(self, frame, *, wrong_panel=False, wrong_checker=False, size=(640, 360)):
        image = Image.new("RGB", size, (17, 19, 23))
        draw = ImageDraw.Draw(image)
        checker = (
            (255, 0, 255), (0, 255, 0),
            (0, 255, 255), (255, 128, 0),
        )
        for y in range(4):
            for x in range(8):
                color = checker[(x & 1) | ((y & 1) << 1)]
                if wrong_checker and x == 0 and y == 0:
                    color = (1, 1, 1)
                draw.rectangle(
                    (128 + 32*x, 64 + 32*y, 128 + 32*(x+1)-1, 64 + 32*(y+1)-1),
                    fill=color,
                )
        for y, row in enumerate(verifier.EXPECTED_ROWS):
            for x, color in enumerate(row):
                if wrong_panel and y == 3 and x == 3:
                    color = (1, 1, 1)
                draw.rectangle(
                    (16 + 16*x, 16 + 16*y, 16 + 16*(x+1)-1, 16 + 16*(y+1)-1),
                    fill=color,
                )
        path = self.directory / f"raster-frame-{frame:04}.png"
        image.save(path, format="PNG")
        return path

    def test_three_correct_synthetic_captures_pass(self):
        for index in verifier.FRAMES:
            self._capture(index)
        report = verifier.check_padding_frames(self.directory)
        self.assertEqual(report["guest_frame_count"], 3)
        self.assertEqual(report["verified_samples_per_frame"], 16)
        self.assertTrue(report["stage224_padded_rgb_opaque_black_verified"])
        self.assertFalse(report["native_gpu_texture_submission_verified"])
        self.assertFalse(report["original_ios_runtime_pixel_parity_verified"])

    def test_missing_guest_frame_is_rejected(self):
        self._capture(30)
        self._capture(300)
        with self.assertRaises(FileNotFoundError):
            verifier.check_padding_frames(self.directory)

    def test_corrupted_padded_region_is_rejected(self):
        self._capture(30)
        self._capture(120, wrong_panel=True)
        self._capture(300)
        with self.assertRaisesRegex(ValueError, "padded PNG sample"):
            verifier.check_padding_frames(self.directory)

    def test_existing_checker_must_still_match(self):
        self._capture(30)
        self._capture(120, wrong_checker=True)
        self._capture(300)
        with self.assertRaisesRegex(ValueError, "expected"):
            verifier.check_padding_frames(self.directory)

    def test_wrong_capture_size_is_rejected(self):
        self._capture(30, size=(641, 360))
        with self.assertRaisesRegex(ValueError, "unexpected size"):
            verifier.check_padding_frame(
                self.directory / "raster-frame-0030.png", 30
            )

    def test_non_png_data_is_rejected(self):
        path = self.directory / "raster-frame-0030.png"
        path.write_bytes(b"not a PNG file")
        with self.assertRaises(Exception):
            verifier.check_padding_frame(path, 30)


if __name__ == "__main__":
    unittest.main()
