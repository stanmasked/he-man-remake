"""Stage235 tests use synthetic bytes and cannot prove runtime GPU execution."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import analyze_stage235_gpu_capture as m
from stage231_capture_session import payload

EXPECTED=payload()
NONCE="b"*32


class Stage235Tests(unittest.TestCase):
    def test_exact_upload_and_render(self):
        report=m.analyze(EXPECTED,EXPECTED)
        self.assertTrue(report["captures"]["upload"]["matches_fixture_exactly"])
        self.assertTrue(report["captures"]["render"]["matches_fixture_exactly"])
        self.assertEqual(report["triage_hint"],"both_captures_match_fixture")
        self.assertFalse(report["evidence_boundary"]["runtime_gpu_execution_attested"])

    def test_vertical_flip_identified_exactly(self):
        flipped=m.transform_expected(EXPECTED,False,True,(0,1,2,3))
        report=m.analyze(EXPECTED,flipped)
        result=report["captures"]["render"]["transform_analysis"]
        self.assertIn("flip_y",result["exact_candidate_transforms"])
        self.assertFalse(report["captures"]["render"]["matches_fixture_exactly"])
        self.assertEqual(report["triage_hint"],
                         "upload_matches_fixture_divergence_appears_after_upload_path")

    def test_horizontal_flip_identified(self):
        flipped=m.transform_expected(EXPECTED,True,False,(0,1,2,3))
        result=m.classify(flipped,EXPECTED)
        self.assertIn("flip_x",result["exact_candidate_transforms"])

    def test_channel_swizzle_identified(self):
        swapped=m.transform_expected(EXPECTED,False,False,(2,1,0,3))
        result=m.classify(swapped,EXPECTED)
        self.assertIn("channels_BGRA",result["exact_candidate_transforms"])

    def test_flip_and_channel_swizzle_identified(self):
        swapped=m.transform_expected(EXPECTED,True,True,(2,1,0,3))
        result=m.classify(swapped,EXPECTED)
        self.assertIn("flip_x+flip_y+channels_BGRA",
                      result["exact_candidate_transforms"])

    def test_per_row_mismatch_counts(self):
        bad=bytearray(EXPECTED)
        bad[(3*16+4)*4+1]^=1
        stats=m.diff_stats(bytes(bad),EXPECTED)
        self.assertEqual(stats["mismatched_bytes"],1)
        self.assertEqual(stats["mismatched_pixels"],1)
        self.assertEqual(stats["row_mismatch_pixels"][3],1)
        self.assertEqual(sum(stats["row_mismatch_pixels"]),1)
        self.assertEqual(stats["first_mismatches"][0]["x"],4)
        self.assertEqual(stats["first_mismatches"][0]["y"],3)

    def test_both_captures_same_wrong_data(self):
        bad=bytes([0xA5])*512
        report=m.analyze(bad,bad)
        self.assertTrue(report["upload_vs_render"]["byte_identical"])
        self.assertEqual(report["triage_hint"],
            "both_captures_share_same_deviation_investigate_transfer_before_sampler")

    def test_capture_files_must_be_exactly_512_bytes(self):
        for bad in (b"",EXPECTED[:-1],EXPECTED+b"x"):
            with self.subTest(length=len(bad)),self.assertRaises(m.DiagnosticError):
                m.analyze(bad,None)
            with self.subTest(render_length=len(bad)),self.assertRaises(m.DiagnosticError):
                m.analyze(None,bad)

    def test_requires_at_least_one_capture(self):
        with self.assertRaisesRegex(m.DiagnosticError,"at least one"):
            m.analyze(None,None)

    def test_phase_is_reported_as_untrusted(self):
        phase=(f"STAGE234_GPU_PHASE nonce={NONCE} phase=04_upload_pixels_match\n"
               .encode("ascii"))
        report=m.analyze(EXPECTED,None,phase)
        self.assertTrue(report["phase"]["syntax_valid"])
        self.assertEqual(report["phase"]["phase"],"04_upload_pixels_match")
        self.assertEqual(report["phase"]["nonce"],NONCE)
        self.assertIn("untrusted",report["phase"]["interpretation"])

    def test_malformed_phase_is_diagnostic_not_attestation(self):
        report=m.analyze(EXPECTED,None,b"STAGE234_GPU_PHASE fake\n")
        self.assertFalse(report["phase"]["syntax_valid"])
        self.assertIsNone(report["phase"]["nonce"])
        self.assertFalse(report["evidence_boundary"]["runtime_gpu_execution_attested"])

    def test_oversized_phase_rejected(self):
        with self.assertRaisesRegex(m.DiagnosticError,"exceeds"):
            m.analyze(EXPECTED,None,b"x"*257)

    def test_render_phase_progress_is_conservative_and_ordered(self):
        cases = (
            ("05_render_commands_submitted", 5, "wait_for_render_queue_idle"),
            ("06_render_queue_idle", 6, "cpu_readback_compare_and_commit_receipt"),
            ("07_receipt_committed", 7, None),
        )
        for phase_name, index, next_expected in cases:
            phase = (f"STAGE234_GPU_PHASE nonce={NONCE} phase={phase_name}\\n"
                     .encode("ascii"))
            with self.subTest(phase=phase_name):
                report = m.analyze(EXPECTED, None, phase)
                details = report["phase"]
                self.assertTrue(details["syntax_valid"])
                self.assertTrue(details["known_phase"])
                self.assertEqual(details["phase_index"], index)
                self.assertEqual(details["next_expected"], next_expected)
                self.assertFalse(details["runtime_gpu_execution_attested"])
                self.assertFalse(details["original_ios_graphics_parity_attested"])
                self.assertIn("not", details["progress_interpretation"])

    def test_unknown_but_well_formed_phase_is_not_assigned_progress(self):
        phase = (f"STAGE234_GPU_PHASE nonce={NONCE} phase=99_future_phase\\n"
                 .encode("ascii"))
        details = m.analyze(EXPECTED, None, phase)["phase"]
        self.assertTrue(details["syntax_valid"])
        self.assertFalse(details["known_phase"])
        self.assertIsNone(details["phase_index"])
        self.assertIsNone(details["next_expected"])
        self.assertFalse(details["runtime_gpu_execution_attested"])

    def test_nonmatching_data_has_ranked_candidates(self):
        bad=bytes([0xA5])*512
        result=m.classify(bad,EXPECTED)
        self.assertEqual(result["exact_candidate_transforms"],[])
        self.assertEqual(len(result["best_candidate_transforms"]),3)
        self.assertGreaterEqual(
            result["best_candidate_transforms"][0]["mismatched_pixels"],1)


if __name__=="__main__":
    unittest.main()
