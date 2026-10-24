"""Stage234 nonce checkpoint and cache barrier audit. Invented data only."""
import importlib.util
import json
from pathlib import Path
import unittest

module_path=Path(__file__).resolve().parents[1]/"tools"/"verify_stage234_gpu_phase.py"
spec=importlib.util.spec_from_file_location("stage234_phase",module_path)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NONCE="9"*32
SESSION={"schema":"stage231-capture-session-v1","nonce":NONCE,
         "nro_sha256":"a"*64}
RECEIPT=("STAGE230_GPU_READBACK width=16 height=8 bytes=512 "
         f"pixels=128 mismatches=0 nonce={NONCE}\n")


def marker(phase):
    return f"STAGE234_GPU_PHASE nonce={NONCE} phase={phase}\n".encode("ascii")


class PhaseTests(unittest.TestCase):
    def test_valid_early_phases_are_not_gpu_execution(self):
        for i,phase in enumerate(m.PHASES[:-1],start=1):
            with self.subTest(phase=phase):
                result=m.check(marker(phase),SESSION)
                self.assertEqual(result["phase_index"],i)
                self.assertFalse(result["completed"])
                self.assertFalse(result["gpu_execution_independently_attested"])

    def test_complete_with_matching_receipt(self):
        result=m.check(marker(m.PHASES[-1]),SESSION,RECEIPT,
                       require_complete=True)
        self.assertTrue(result["completed"])
        self.assertFalse(result["gpu_execution_independently_attested"])

    def test_incomplete_cannot_pass_final_gate(self):
        with self.assertRaisesRegex(m.PhaseEvidenceError,"never reached"):
            m.check(marker(m.PHASES[-2]),SESSION,RECEIPT,
                    require_complete=True)

    def test_completed_without_receipt_rejected(self):
        with self.assertRaisesRegex(m.PhaseEvidenceError,"without guest receipt"):
            m.check(marker(m.PHASES[-1]),SESSION)
        with self.assertRaisesRegex(m.PhaseEvidenceError,"missing/stale"):
            m.check(marker(m.PHASES[-1]),SESSION,RECEIPT.replace(NONCE,"e"*32))

    def test_oversize_corruption_wrong_session_unknown_phase(self):
        bad=[
            b"",
            marker(m.PHASES[0])+b"additional line\n",
            marker(m.PHASES[0])*5,
            marker(m.PHASES[0]).replace(b"nonce="+NONCE.encode(),b"nonce="+b"a"*32),
            marker(m.PHASES[0]).replace(b"01_nonce_validated",b"99_no_such_step"),
            marker(m.PHASES[0]).replace(b"STAGE234_",b"STAGE999_"),
            marker(m.PHASES[0]).replace(b" phase=",b"\nphase="),
        ]
        for sample in bad:
            with self.subTest(size=len(sample)),self.assertRaises(m.PhaseEvidenceError):
                m.check(sample,SESSION)

    def test_malformed_manifest(self):
        for manifest in ({},dict(SESSION,nonce="0"*32),
                         dict(SESSION,schema="stage230-gpu-run-v1")):
            with self.subTest(manifest=manifest),self.assertRaises(m.PhaseEvidenceError):
                m.check(marker(m.PHASES[0]),manifest)

    def test_compiled_cpp_source_preflight(self):
        cpp=(Path(__file__).resolve().parents[1]/
             "switch_gpu_png"/"source"/"main.cpp").read_text(encoding="utf-8")
        result=m.audit_source(cpp)
        self.assertEqual(result["checkpoint_count"],7)
        self.assertFalse(result["gpu_executed"])

    def test_omit_texture_cache_flag_rejected(self):
        source=(Path(__file__).resolve().parents[1]/
                "switch_gpu_png"/"source"/"main.cpp").read_text()
        bad=source.replace("DkInvalidateFlags_Image|DkInvalidateFlags_Descriptors|",
                           "DkInvalidateFlags_Descriptors|")
        with self.assertRaises(m.PhaseEvidenceError):
            m.audit_source(bad)

    def test_swap_main_phases_rejected(self):
        source=(Path(__file__).resolve().parents[1]/
                "switch_gpu_png"/"source"/"main.cpp").read_text()
        first='saveStage234Checkpoint("01_nonce_validated")'
        second='saveStage234Checkpoint("02_shaders_loaded")'
        scrambled=source.replace(first,"TEMP_A").replace(second,first).replace("TEMP_A",second)
        with self.assertRaisesRegex(m.PhaseEvidenceError,"out of order"):
            m.audit_source(scrambled)

    def test_source_multiple_call_and_wrong_render_barrier(self):
        source=(Path(__file__).resolve().parents[1]/
                "switch_gpu_png"/"source"/"main.cpp").read_text()
        duplicated=source.replace('saveStage234Checkpoint("06_render_queue_idle")',
                                  'saveStage234Checkpoint("05_render_queue_idle") && saveStage234Checkpoint("05_render_queue_idle")')
        with self.assertRaises(m.PhaseEvidenceError):
            m.audit_source(duplicated)
        no_full=source.replace("cmd.barrier(DkBarrier_Full,",
                               "cmd.barrier(DkBarrier_None,",1)
        with self.assertRaises(m.PhaseEvidenceError):
            m.audit_source(no_full)


if __name__=="__main__":
    unittest.main()
