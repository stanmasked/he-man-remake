"""Static mutation probes: no test here runs NeXium or fabricates guest PNGs."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from instrument_nexium_three_room import FRAMES, HID_EVENTS
from verify_three_room_hid_parity import (
    HOST_SOURCES, c_hid_events, c_sample_frames, verify,
)


class ThreeRoomHidScheduleParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for rel in HOST_SOURCES + (
            ".github/workflows/nexium-patched-three-room.yml",
        ):
            destination = self.root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text((ROOT / rel).read_text())

    def replace_file(self, rel: str, old: str, new: str):
        file = self.root / rel
        original = file.read_text()
        self.assertIn(old, original)
        file.write_text(original.replace(old, new, 1))

    def test_complete_unmodified_native_and_python_contract(self):
        result = verify(self.root)
        self.assertEqual(result["controller_edges"], 16)
        self.assertEqual(result["capture_frames"], 18)
        self.assertTrue(result["pixel_samples_match_guest_script"])
        self.assertFalse(result["real_nexium_guest_verified"])

    def test_C99_both_sources_replay_exact_authoritative_events(self):
        for rel in HOST_SOURCES:
            with self.subTest(path=rel):
                observed = c_hid_events((self.root / rel).read_text())
                self.assertEqual(observed, HID_EVENTS)

    def test_C99_raster_sample_frames_are_exact(self):
        source = (self.root / HOST_SOURCES[1]).read_text()
        self.assertEqual(c_sample_frames(source), FRAMES)

    def test_changed_third_room_jump_in_C99_rejected(self):
        self.replace_file(
            HOST_SOURCES[0], "case 350u:case 952u:return R|A;",
            "case 350u:case 953u:return R|A;",
        )
        with self.assertRaisesRegex(ValueError, "HID mismatch"):
            verify(self.root)

    def test_changed_second_room_release_in_raster_rejected(self):
        self.replace_file(
            HOST_SOURCES[1],
            "case 78u:case 95u:case 470u:case 515u:",
            "case 78u:case 95u:case 500u:case 515u:",
        )
        with self.assertRaisesRegex(ValueError, "HID mismatch"):
            verify(self.root)

    def test_C99_unknown_instruction_is_not_silently_skipped(self):
        self.replace_file(
            HOST_SOURCES[0], "case 353u:case 955u:return R;",
            "case 353u:case 955u:return R|ZL;",
        )
        with self.assertRaisesRegex(ValueError, "Unsupported C99"):
            verify(self.root)

    def test_C99_duplicate_frame_rejected(self):
        self.replace_file(
            HOST_SOURCES[0], "case 45u:case 110u:case 530u: return R;",
            "case 45u:case 110u:case 530u:case 45u: return R;",
        )
        with self.assertRaisesRegex(ValueError, "Duplicate C99"):
            verify(self.root)

    def test_Python_schedule_must_match_native_not_just_be_valid(self):
        changed = tuple(
            (500 if f == 470 else f, action)
            for f, action in HID_EVENTS
        )
        with self.assertRaisesRegex(ValueError, "post-CLEAR release"):
            verify(self.root, hid_events=tuple(sorted(changed)))

    def test_C99_capture_frame_drift_rejected(self):
        self.replace_file(
            HOST_SOURCES[1], "1120u,1170u,1190u",
            "1120u,1170u,1191u",
        )
        with self.assertRaisesRegex(ValueError, "frame samples diverge"):
            verify(self.root)

    def test_workflow_must_still_inject_HID_and_capture_real_PNG(self):
        self.replace_file(
            ".github/workflows/nexium-patched-three-room.yml",
            "NEXIUM_HID_INJECT_EXCLUSIVE",
            "NEXIUM_HID_INJECT_DISABLED",
        )
        with self.assertRaisesRegex(ValueError, "no longer uses"):
            verify(self.root)

    def test_unscheduled_extra_C99_case_rejected(self):
        self.replace_file(
            HOST_SOURCES[0], "case 353u:case 955u:return R;",
            "case 353u:case 955u:case 1111u:return R;",
        )
        with self.assertRaisesRegex(ValueError, "HID mismatch"):
            verify(self.root)

    def test_duplicate_Python_frame_rejected(self):
        invalid = HID_EVENTS + ((1140, "buttons=A"),)
        with self.assertRaisesRegex(ValueError, "strictly ordered|repeated"):
            verify(self.root, hid_events=invalid)


if __name__ == "__main__":
    unittest.main()
