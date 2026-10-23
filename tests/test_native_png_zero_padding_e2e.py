"""Stage223: source-free end-to-end CPU preview with padded PNGs."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from heman_tools.private_cpu_frame_preview import render_private_cpu_frame_preview
from test_private_multisymbol_frame_audit import _synthetic_multisymbol_ipa


class PaddedPNGFrameTests(unittest.TestCase):
    def test_synthetic_padded_png_renders_without_raw_stride_mismatch(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "padded-synthetic.ipa"
            regions = _synthetic_multisymbol_ipa(ipa, png_size=(17, 16))
            for screen in ("screen-med", "screen-xlarge"):
                report, frame = render_private_cpu_frame_preview(
                    ipa, regions, "syntheticIdle", 0, "east", 0,
                    screen=screen,
                )
                self.assertEqual(report["native_zero_padded_texture_bindings"], 2)
                self.assertTrue(report["native_rgb_vs_rgba_padding_distinguished"])
                self.assertTrue(report["native_texture_sampling_uses_allocated_dimensions"])
                self.assertGreater(frame.pixel_samples, 0)
                self.assertFalse(report["gpu_submission_verified"])
                self.assertFalse(report["original_runtime_pixel_parity_verified"])


if __name__ == "__main__":
    unittest.main()
