"""Stage236 bundle tests use invented captures and fake NRO bytes only."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import collect_stage236_gpu_bundle as m
from stage231_capture_session import payload

NONCE="c"*32
NRO=bytes(16)+b"NRO0"+b"stage236-fake-test-nro"
NRO_SHA=hashlib.sha256(NRO).hexdigest()
RECEIPT=("STAGE230_GPU_READBACK width=16 height=8 bytes=512 "
         f"pixels=128 mismatches=0 nonce={NONCE}\n")
PHASE=f"STAGE234_GPU_PHASE nonce={NONCE} phase=07_receipt_committed\n".encode()
GUEST=f"STAGE241_GUEST_EXIT nonce={NONCE} code=0\n".encode()
DEFAULT=object()


class BundleTests(unittest.TestCase):
    def prepare(self,root,*,upload=DEFAULT,render=DEFAULT,phase=PHASE,receipt=RECEIPT,
                guest_exit=GUEST,sd_nonce=NONCE+"\n",session_nonce=NONCE,nro_sha=NRO_SHA,
                session_schema="stage231-capture-session-v1"):
        root=Path(root)
        sd=root/"sd"/"switch"/"heman-stage230"
        sd.mkdir(parents=True,exist_ok=True)
        session=root/"private"
        session.mkdir(parents=True,exist_ok=True)
        nro=root/"heman.nro"
        nro.write_bytes(NRO)
        manifest={"schema":session_schema,"nonce":session_nonce,
                  "nro_sha256":nro_sha,"runtime_provenance_attested":False}
        (session/"stage231_session.json").write_text(json.dumps(manifest),encoding="utf-8")
        values={"upload":payload() if upload is DEFAULT else upload,
                "render":payload() if render is DEFAULT else render,
                "phase":phase,"receipt":receipt,"guest_exit":guest_exit,
                "sd_nonce":sd_nonce.encode("ascii") if isinstance(sd_nonce,str) else sd_nonce}
        names={"upload":"upload.rgba","render":"readback.rgba",
               "phase":"gpu_phase.txt","receipt":"readback.receipt",
               "guest_exit":"guest_exit.txt",
               "sd_nonce":"run_nonce.txt"}
        for key,value in values.items():
            path=sd/names[key]
            if value is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(value if isinstance(value,bytes) else value.encode("ascii"))
        return nro,root/"sd",session

    def collect(self,root,**kwargs):
        nro,sd,session=self.prepare(root,**kwargs)
        return m.collect_bundle(nro,sd,session)

    def attach_collected(self,session):
        receipt_bytes=RECEIPT.encode("ascii")
        runner=b"synthetic runner log, not a real execution\n"
        (session/"readback.rgba").write_bytes(payload())
        (session/"readback.receipt").write_bytes(receipt_bytes)
        (session/"runtime.log").write_bytes(runner)
        (session/"exit-status.txt").write_text("0\n",encoding="ascii")
        report={
            "schema":"stage231-collected-synthetic-gpu-evidence-v1",
            "result":"submitted_capture_matches_challenge_and_pixels",
            "nonce":NONCE,"nro_sha256":NRO_SHA,
            "rgba_sha256":hashlib.sha256(payload()).hexdigest(),
            "receipt_sha256":hashlib.sha256(receipt_bytes).hexdigest(),
            "runner_log_sha256":hashlib.sha256(runner).hexdigest(),
            "runtime_provenance_attested":False,
        }
        (session/"stage231_collected.json").write_text(json.dumps(report),encoding="utf-8")

    def test_complete_consistent_bundle_is_not_gpu_attestation(self):
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root)
        gate=report["consistency_gate"]
        self.assertTrue(gate["synthetic_bundle_consistent"])
        self.assertTrue(gate["stage241_guest_reported_success"])
        self.assertEqual(report["guest_exit"]["guest_exit_code"],0)
        self.assertTrue(gate["both_upload_and_render_match_synthetic_fixture"])
        self.assertFalse(gate["runtime_gpu_execution_attested"])
        self.assertFalse(gate["original_ios_graphics_parity_attested"])

    def test_missing_guest_receipt_fails_even_with_pixel_perfection(self):
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,guest_exit=None)
        self.assertTrue(report["receipt"]["zero_pixel_mismatches"])
        self.assertTrue(report["consistency_gate"]["both_upload_and_render_match_synthetic_fixture"])
        self.assertFalse(report["consistency_gate"]["stage241_guest_reported_success"])
        self.assertFalse(report["session_links"]["all_session_links_match"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])
        self.assertEqual(report["guest_exit"]["status"],"missing")

    def test_nonzero_guest_return_fails_even_if_captures_match(self):
        receipt=GUEST.replace(b"code=0",b"code=25")
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,guest_exit=receipt)
        self.assertEqual(report["guest_exit"]["guest_exit_code"],25)
        self.assertFalse(report["consistency_gate"]["stage241_guest_reported_success"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_stale_guest_nonce_fails_session_link(self):
        receipt=GUEST.replace(NONCE.encode("ascii"),b"d"*32)
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,guest_exit=receipt)
        self.assertEqual(report["guest_exit"]["status"],"nonce_mismatch")
        self.assertFalse(report["session_links"]["guest_exit_nonce_matches_session"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_malformed_guest_receipt_preserves_diagnostics(self):
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,guest_exit=b"truncated")
        self.assertEqual(report["guest_exit"]["status"],"malformed")
        self.assertIn("upload",report["pixel_diagnostics"]["captures"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_missing_partial_files_remain_diagnostic(self):
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,upload=None,render=None,phase=None,receipt=None,
                                sd_nonce=None)
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])
        self.assertEqual(report["files"]["upload"]["status"],"missing")
        self.assertEqual(report["phase"]["status"],"missing_or_unreadable")
        self.assertIsNone(report["pixel_diagnostics"])

    def test_phase_index_follows_runtime_order_not_alphabetical_order(self):
        cases = (
            ("05_render_commands_submitted", 5, "wait_for_render_queue_idle"),
            ("06_render_queue_idle", 6, "cpu_readback_compare_and_commit_receipt"),
            ("07_receipt_committed", 7, None),
        )
        for phase_name, index, next_expected in cases:
            phase = f"STAGE234_GPU_PHASE nonce={NONCE} phase={phase_name}\n".encode()
            with self.subTest(phase=phase_name), tempfile.TemporaryDirectory() as root:
                report = self.collect(root, phase=phase)
                self.assertEqual(report["phase"]["phase_index"], index)
                self.assertEqual(report["phase"]["next_expected"], next_expected)
                self.assertTrue(report["phase"]["known_phase"])
                self.assertFalse(report["phase"]["runtime_gpu_execution_attested"])

    def test_wrong_phase_nonce_rejected_by_consistency_gate(self):
        stale=f"STAGE234_GPU_PHASE nonce={'d'*32} phase=07_receipt_committed\n".encode()
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,phase=stale)
        self.assertFalse(report["session_links"]["phase_nonce_matches_session"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_wrong_receipt_nonce_rejected(self):
        stale=RECEIPT.replace(NONCE,"d"*32)
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,receipt=stale)
        self.assertFalse(report["session_links"]["receipt_nonce_matches_session"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_wrong_sd_nonce_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,sd_nonce="d"*32+"\n")
        self.assertFalse(report["session_links"]["sd_nonce_matches_session"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_wrong_nro_digest_prevents_acceptance(self):
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,nro_sha="0"*64)
        self.assertFalse(report["session"]["nro_matches_prepared_session"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_upload_mismatch_is_preserved_and_diagnosed(self):
        bad=bytearray(payload())
        bad[22]^=1
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,upload=bytes(bad))
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])
        self.assertFalse(report["pixel_diagnostics"]["captures"]["upload"]["matches_fixture_exactly"])
        self.assertEqual(report["pixel_diagnostics"]["triage_hint"],
            "captures_differ_review_upload_and_draw_paths")

    def test_same_wrong_captures_report_shared_deviation(self):
        bad=bytes([0xA5])*512
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,upload=bad,render=bad)
        self.assertEqual(report["pixel_diagnostics"]["triage_hint"],
            "both_captures_share_same_deviation_investigate_transfer_before_sampler")

    def test_receipt_nonzero_mismatch_is_structurally_valid_but_not_clean(self):
        dirty=RECEIPT.replace("mismatches=0","mismatches=7")
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,receipt=dirty)
        self.assertEqual(report["receipt"]["status"],"valid")
        self.assertFalse(report["receipt"]["zero_pixel_mismatches"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_malformed_capture_size_is_not_used_as_pixels(self):
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,upload=payload()[:-1])
        self.assertFalse(report["files"]["upload"]["size_valid"])
        self.assertNotIn("upload",report["pixel_diagnostics"]["captures"])
        self.assertIn("render",report["pixel_diagnostics"]["captures"])

    def test_oversized_phase_does_not_discard_capture_diagnostics(self):
        with tempfile.TemporaryDirectory() as root:
            report=self.collect(root,phase=b"x"*257)
        self.assertEqual(report["phase"]["status"],"oversized")
        self.assertIn("upload",report["pixel_diagnostics"]["captures"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])

    def test_oversized_private_log_is_inventory_only_and_fails_hash_join(self):
        with tempfile.TemporaryDirectory() as root:
            nro,sd,session=self.prepare(root)
            self.attach_collected(session)
            with (session/"runtime.log").open("wb") as out:
                out.truncate(4*1024*1024+1)
            report=m.collect_bundle(nro,sd,session)
        self.assertEqual(report["files"]["runtime_log"]["status"],"oversized")
        self.assertFalse(report["stage231_collected_report"]["runner_log_hash_matches"])
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])
        self.assertIn("render",report["pixel_diagnostics"]["captures"])

    def test_oversized_receipt_guest_and_nonce_keep_other_diagnostics(self):
        with tempfile.TemporaryDirectory() as root:
            nro,sd,session=self.prepare(root)
            capture=sd/"switch"/"heman-stage230"
            (capture/"readback.receipt").write_bytes(b"x"*257)
            (capture/"guest_exit.txt").write_bytes(b"x"*129)
            (capture/"run_nonce.txt").write_bytes(b"z"*65)
            report=m.collect_bundle(nro,sd,session)
        for label in ("receipt","guest_exit","sd_nonce"):
            self.assertEqual(report["files"][label]["status"],"oversized")
        self.assertEqual(report["guest_exit"]["status"],"oversized_or_unreadable")
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])
        self.assertIn("upload",report["pixel_diagnostics"]["captures"])

    def test_oversized_collected_json_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as root:
            nro,sd,session=self.prepare(root)
            with (session/"stage231_collected.json").open("wb") as out:
                out.truncate(64*1024+1)
            report=m.collect_bundle(nro,sd,session)
        self.assertEqual(report["stage231_collected_report"]["status"],"invalid")
        self.assertFalse(report["consistency_gate"]["synthetic_bundle_consistent"])
        self.assertIn("upload",report["pixel_diagnostics"]["captures"])

    def test_bad_session_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(m.BundleError,"schema"):
                self.collect(root,session_schema="wrong-schema")

    def test_collected_report_is_not_gpu_attestation(self):
        with tempfile.TemporaryDirectory() as root:
            nro,sd,session=self.prepare(root)
            self.attach_collected(session)
            result=m.collect_bundle(nro,sd,session)
        self.assertEqual(result["stage231_collected_report"]["status"],"valid")
        self.assertTrue(result["stage231_collected_report"]["receipt_hash_matches"])
        self.assertTrue(result["stage231_collected_report"]["runner_log_hash_matches"])
        self.assertTrue(result["stage231_collected_report"]["exit_status_zero"])
        self.assertFalse(result["stage231_collected_report"]["runtime_provenance_attested"])

    def test_collected_runner_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            nro,sd,session=self.prepare(root)
            self.attach_collected(session)
            (session/"runtime.log").write_bytes(b"tampered runner log\n")
            result=m.collect_bundle(nro,sd,session)
        self.assertEqual(result["stage231_collected_report"]["status"],"mismatch")
        self.assertFalse(result["stage231_collected_report"]["runner_log_hash_matches"])
        self.assertFalse(result["consistency_gate"]["stage231_collected_report_consistent_if_present"])
        self.assertFalse(result["consistency_gate"]["synthetic_bundle_consistent"])


if __name__=="__main__":
    unittest.main()
