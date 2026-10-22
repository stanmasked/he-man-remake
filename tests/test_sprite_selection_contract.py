"""Synthetic-only tests for Stage186 directional sequence selection."""
from __future__ import annotations

import unittest

from heman_tools.sprite_selection_contract import decide_directional_selection


SLOTS = ("synthetic-slot-0", "synthetic-slot-1",
         "synthetic-slot-2", "synthetic-slot-3")


class DirectionalSelectionContractTests(unittest.TestCase):
    def test_selector_0_uses_storage_slot_0(self):
        decision = decide_directional_selection(SLOTS, 0, reset_to_first_frame=False)
        self.assertEqual(decision.slot_index, 0)
        self.assertEqual(decision.resource_key, SLOTS[0])
        self.assertTrue(decision.starts_playback)
        self.assertFalse(decision.clears_current_sequence)

    def test_selector_1_uses_storage_slot_1(self):
        decision = decide_directional_selection(SLOTS, 1, reset_to_first_frame=False)
        self.assertEqual(decision.slot_index, 1)
        self.assertEqual(decision.resource_key, SLOTS[1])

    def test_selector_2_uses_storage_slot_3(self):
        decision = decide_directional_selection(SLOTS, 2, reset_to_first_frame=False)
        self.assertEqual(decision.slot_index, 3)
        self.assertEqual(decision.resource_key, SLOTS[3])

    def test_selector_3_uses_storage_slot_2(self):
        decision = decide_directional_selection(SLOTS, 3, reset_to_first_frame=False)
        self.assertEqual(decision.slot_index, 2)
        self.assertEqual(decision.resource_key, SLOTS[2])

    def test_invalid_negative_selector_clears_without_fallback(self):
        decision = decide_directional_selection(SLOTS, -1, reset_to_first_frame=False)
        self.assertIsNone(decision.slot_index)
        self.assertIsNone(decision.resource_key)
        self.assertTrue(decision.clears_current_sequence)
        self.assertFalse(decision.starts_playback)

    def test_invalid_high_selector_clears_without_fallback(self):
        decision = decide_directional_selection(SLOTS, 4, reset_to_first_frame=False)
        self.assertIsNone(decision.slot_index)
        self.assertIsNone(decision.resource_key)
        self.assertTrue(decision.clears_current_sequence)

    def test_missing_selected_slot_clears_without_fallback(self):
        slots = ("synthetic-slot-0", None, "synthetic-slot-2", "synthetic-slot-3")
        decision = decide_directional_selection(slots, 1, reset_to_first_frame=False)
        self.assertEqual(decision.slot_index, 1)
        self.assertIsNone(decision.resource_key)
        self.assertTrue(decision.clears_current_sequence)
        self.assertFalse(decision.starts_playback)

    def test_missing_nonselected_slot_does_not_affect_selection(self):
        slots = ("synthetic-slot-0", None, "synthetic-slot-2", "synthetic-slot-3")
        decision = decide_directional_selection(slots, 0, reset_to_first_frame=False)
        self.assertEqual(decision.resource_key, slots[0])
        self.assertTrue(decision.starts_playback)
        self.assertFalse(decision.clears_current_sequence)

    def test_reset_flag_is_preserved_when_sequence_is_selected(self):
        decision = decide_directional_selection(SLOTS, 2, reset_to_first_frame=True)
        self.assertTrue(decision.reset_to_first_frame)

    def test_reset_flag_is_preserved_when_sequence_is_cleared(self):
        decision = decide_directional_selection(SLOTS, 99, reset_to_first_frame=True)
        self.assertTrue(decision.reset_to_first_frame)
        self.assertTrue(decision.clears_current_sequence)

    def test_exactly_four_slots_are_required(self):
        with self.assertRaisesRegex(ValueError, "Exactly four"):
            decide_directional_selection(SLOTS[:3], 0, reset_to_first_frame=False)

    def test_empty_resource_key_is_rejected(self):
        slots = ("synthetic-slot-0", "", "synthetic-slot-2", "synthetic-slot-3")
        with self.assertRaisesRegex(ValueError, "non-empty keys"):
            decide_directional_selection(slots, 0, reset_to_first_frame=False)

    def test_boolean_is_not_accepted_as_selector(self):
        with self.assertRaisesRegex(ValueError, "selector must be an integer"):
            decide_directional_selection(SLOTS, True, reset_to_first_frame=False)

    def test_reset_flag_must_be_boolean(self):
        with self.assertRaisesRegex(ValueError, "Reset flag must be boolean"):
            decide_directional_selection(SLOTS, 0, reset_to_first_frame=1)


if __name__ == "__main__":
    unittest.main()
