"""Stage250 shared phase contract tests use invented marker bytes only."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import stage234_phase_contract as contract
import analyze_stage235_gpu_capture as analyzer
import collect_stage236_gpu_bundle as bundle
from stage231_capture_session import payload

NONCE = "e" * 32


class Stage250PhaseContractTests(unittest.TestCase):
    def test_phase_order_is_explicit_and_unique(self):
        self.assertEqual(len(contract.PHASES), 7)
        self.assertEqual(len(set(contract.PHASES)), 7)
        self.assertEqual(
            contract.PHASES,
            (
                "01_nonce_validated",
                "02_shaders_loaded",
                "03_texture_upload_queue_idle",
                "04_upload_pixels_match",
                "05_render_commands_submitted",
                "06_render_queue_idle",
                "07_receipt_committed",
            ),
        )

    def test_all_consumers_use_the_same_runtime_order(self):
        fixture = payload()
        for index, phase in enumerate(contract.PHASES, start=1):
            marker = f"STAGE234_GPU_PHASE nonce={NONCE} phase={phase}\n".encode("ascii")
            with self.subTest(phase=phase):
                description = contract.describe_phase(phase)
                analyzed = analyzer.analyze(fixture, None, marker)["phase"]
                collected = bundle.phase_info(marker, NONCE)
                self.assertEqual(description["phase_index"], index)
                self.assertEqual(analyzed["phase_index"], index)
                self.assertEqual(collected["phase_index"], index)
                self.assertEqual(analyzed["next_expected"], description["next_expected"])
                self.assertEqual(collected["next_expected"], description["next_expected"])
                self.assertFalse(description["runtime_gpu_execution_attested"])
                self.assertFalse(analyzed["runtime_gpu_execution_attested"])
                self.assertFalse(collected["runtime_gpu_execution_attested"])
                self.assertFalse(description["original_ios_graphics_parity_attested"])

    def test_submit_and_queue_idle_are_not_conflated(self):
        submitted = contract.describe_phase("05_render_commands_submitted")
        idle = contract.describe_phase("06_render_queue_idle")
        receipt = contract.describe_phase("07_receipt_committed")
        self.assertEqual(submitted["phase_index"], 5)
        self.assertEqual(submitted["next_expected"], "wait_for_render_queue_idle")
        self.assertIn("not established", submitted["progress_interpretation"])
        self.assertEqual(idle["phase_index"], 6)
        self.assertEqual(idle["next_expected"], "cpu_readback_compare_and_commit_receipt")
        self.assertIn("not established", idle["progress_interpretation"])
        self.assertEqual(receipt["phase_index"], 7)
        self.assertIsNone(receipt["next_expected"])
        self.assertIn("not independent GPU execution", receipt["progress_interpretation"])

    def test_unknown_phase_has_no_order_or_attestation(self):
        unknown = contract.describe_phase("99_future_phase")
        self.assertFalse(unknown["known_phase"])
        self.assertIsNone(unknown["phase_index"])
        self.assertIsNone(unknown["next_expected"])
        self.assertFalse(unknown["runtime_gpu_execution_attested"])
        marker = f"STAGE234_GPU_PHASE nonce={NONCE} phase=99_future_phase\n".encode("ascii")
        analyzed = analyzer.analyze(payload(), None, marker)["phase"]
        collected = bundle.phase_info(marker, NONCE)
        self.assertTrue(analyzed["syntax_valid"])
        self.assertFalse(analyzed["known_phase"])
        self.assertIsNone(analyzed["phase_index"])
        self.assertEqual(collected["status"], "mismatch")
        self.assertFalse(collected["known_phase"])


if __name__ == "__main__":
    unittest.main()
