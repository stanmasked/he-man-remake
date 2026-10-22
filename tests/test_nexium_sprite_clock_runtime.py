"""Host regressions for the NeXium sprite-clock capture and pixel verifier."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from instrument_nexium_sprite_clock import instrument
from verify_nexium_sprite_clock_pngs import FRAME_INDICES, verify

SOURCE = """
fn sample() {
    for frame in emulation.frame_rx.try_iter() {
            frames += 1;
            if frames <= 3 {
                println!("first");
            }
    }
    for frame in emulation.frame_rx.try_iter() {
        frames += 1;
        if frames <= 3 {
            println!("last");
        }
    }
}
"""

BACKGROUND = (55, 35, 24)
PANEL = (93, 70, 57)
SWATCHES = {
    6: (209, 185, 71),
    12: (91, 196, 122),
    18: (72, 91, 216),
    30: (91, 196, 122),
    36: (91, 196, 122),
    120: (91, 196, 122),
    300: (91, 196, 122),
}
YELLOW = (102, 209, 255)
WHITE = (240, 240, 240)


def make_guest_fixture(folder: Path) -> None:
    for index in FRAME_INDICES:
        image = Image.new("RGB", (640, 360), BACKGROUND)
        px = image.load()

        # The synthetic NRO's large center swatch.
        swatch = SWATCHES[index]
        for y in range(100, 276):
            for x in range(120, 520):
                px[x, y] = swatch

        # The bar backgrounds are visible even when their fill is empty.
        for y in range(76, 84):
            for x in range(40, 600):
                px[x, y] = PANEL
        for y in range(286, 300):
            for x in range(130, 510):
                px[x, y] = PANEL

        # Synthetic elapsed progress bar: elapsed=480 at frame 12,
        # zero after the first replay at 18, 520 at 30, then clamped full.
        if index == 12:
            for x in range(130, 130 + (480 * 380 // 720)):
                px[x, 292] = YELLOW
        elif index == 30:
            for x in range(130, 130 + (520 * 380 // 720)):
                px[x, 292] = YELLOW
        elif index in (36, 120, 300):
            for x in range(130, 510):
                px[x, 292] = YELLOW

        # Native strict-finish strip.
        if index in (36, 120, 300):
            for x in range(40, 600):
                px[x, 352] = WHITE

        # Per-callback update indicator: one quantum at frame 30, two at 120.
        if index == 30:
            for x in range(40, 120):
                px[x, 80] = YELLOW
        elif index == 120:
            for x in range(40, 200):
                px[x, 80] = YELLOW
        image.save(folder / f"raster-frame-{index:04}.png")


class SpriteClockRuntimeInstrumentationTests(unittest.TestCase):
    def test_both_frame_receivers_capture_all_required_checkpoints(self) -> None:
        code = instrument(SOURCE)
        self.assertEqual(code.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(code.count(
            "matches!(frames, 6 | 12 | 18 | 30 | 36 | 120 | 300)"), 2)
        self.assertEqual(code.count("raster-frame-{frames:04}.png"), 2)

    def test_double_instrumentation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "already been instrumented"):
            instrument(instrument(SOURCE))

    def test_changed_upstream_loop_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "source changed"):
            instrument(SOURCE.replace("frames += 1;", "frames += 2;", 1))


class SpriteClockRuntimeWorkflowTests(unittest.TestCase):
    def test_runner_window_covers_delayed_start_and_frame_300(self) -> None:
        workflow = (ROOT / ".github/workflows/nexium-sprite-clock-probe.yml").read_text()
        self.assertIn('NEXIUM_DEBUG_RUNNER_SECONDS: "40"', workflow)
        self.assertIn("timeout --kill-after=6s 95s", workflow)


class SpriteClockGuestPixelVerifierTests(unittest.TestCase):
    def test_valid_synthetic_guest_checkpoint_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            make_guest_fixture(folder)
            result = verify(folder)
        self.assertEqual(result["captured_frames"], list(FRAME_INDICES))
        self.assertEqual(result["center_swatch_rgb"]["6"], [209, 185, 71])
        self.assertEqual(result["center_swatch_rgb"]["18"], [72, 91, 216])
        self.assertTrue(result["progress_bar_reset_at_frame_18"])
        self.assertTrue(result["progress_bar_full_by_frame_36"])
        self.assertTrue(result["finished_strip_stable_after_frame_36"])
        self.assertTrue(result["two_update_catchup_visible_at_frame_120"])

    def test_wrong_center_swatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            make_guest_fixture(folder)
            path = folder / "raster-frame-0012.png"
            with Image.open(path) as source:
                image = source.convert("RGB")
            image.putpixel((320, 180), BACKGROUND)
            image.save(path)
            with self.assertRaisesRegex(
                ValueError, "Unexpected synthetic swatch at frame 12"
            ):
                verify(folder)

    def test_wrong_two_update_bar_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            make_guest_fixture(folder)
            path = folder / "raster-frame-0120.png"
            with Image.open(path) as source:
                image = source.convert("RGB")
            px = image.load()
            for x in range(120, 200):
                px[x, 80] = BACKGROUND
            image.save(path)
            with self.assertRaisesRegex(ValueError, "two catch-up updates"):
                verify(folder)

    def test_finished_strip_appearing_before_strict_end_fails_closed(self) -> None:
        for index in (6, 12, 18, 30):
            with self.subTest(frame=index), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                make_guest_fixture(folder)
                path = folder / f"raster-frame-{index:04}.png"
                with Image.open(path) as source:
                    image = source.convert("RGB")
                image.putpixel((100, 352), WHITE)
                image.save(path)
                with self.assertRaisesRegex(
                    ValueError,
                    f"Finished-state strip appeared before the strict end edge at guest frame {index}",
                ):
                    verify(folder)

    def test_missing_guest_checkpoint_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            make_guest_fixture(folder)
            (folder / "raster-frame-0300.png").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "frame 300"):
                verify(folder)


if __name__ == "__main__":
    unittest.main()
