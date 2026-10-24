"""Stage240 host launcher tests. Fake runners are NOT Switch/GPU evidence."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage240_private_emulator_launcher as m

FAKE_RUNNER=r'''#!/usr/bin/env python3
# Unit-test runner only; fabricates RGBA buffers, executes no GPU instructions.
import pathlib
import subprocess
import sys
root=pathlib.Path(sys.argv[1])/"switch"/"heman-stage230"
nonce=(root/"run_nonce.txt").read_text(encoding="ascii").strip()
mode=sys.argv[3]
if mode=="orphan":
    subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])
    sys.exit(0)
if mode=="noisy":
    for _ in range(100):
        sys.stdout.write("X"*65536)
        sys.stdout.flush()
    sys.exit(0)
print("STAGE240_FAKE_RUNNER_NOT_GPU_EVIDENCE", flush=True)
if mode in ("success","success_no_guest"):
    pixels=bytearray()
    for y in range(8):
        for x in range(16):
            pixels.extend((x*20,y*30,x+y,255) if x<9 and y<5
                          else (0,0,0,255))
    (root/"upload.rgba").write_bytes(pixels)
    (root/"readback.rgba").write_bytes(pixels)
    (root/"readback.receipt").write_text(
        "STAGE230_GPU_READBACK width=16 height=8 bytes=512 "
        "pixels=128 mismatches=0 nonce="+nonce+"\n",encoding="ascii")
    (root/"gpu_phase.txt").write_text(
        "STAGE234_GPU_PHASE nonce="+nonce+
        " phase=07_receipt_committed\n",encoding="ascii")
    if mode=="success":
        (root/"guest_exit.txt").write_text(
            "STAGE241_GUEST_EXIT nonce="+nonce+" code=0\n",encoding="ascii")
elif mode=="incomplete":
    (root/"gpu_phase.txt").write_text(
        "STAGE234_GPU_PHASE nonce="+nonce+
        " phase=02_shaders_loaded\n",encoding="ascii")
if mode=="nonzero":
    sys.exit(7)
'''


class Stage240Tests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name).resolve()
        self.exe=self.root/"synthetic-runner.py"
        self.exe.write_text(FAKE_RUNNER,encoding="utf-8")
        self.exe.chmod(0o700)
        self.nro=self.root/"probe.nro"
        self.nro.write_bytes(bytes(16)+b"NRO0"+b"fixture-only")
        self.sd=self.root/"sd"
        self.sd.mkdir()
        self.session=self.root/"private"/"session"
        self.assertFalse(self.session.exists())

    def args(self, mode):
        return [str(self.sd),"{nro}",mode]

    def test_build_requires_explicit_nro_argument(self):
        with self.assertRaisesRegex(m.LaunchError,"exactly once"):
            m.build_command(self.exe,self.nro,[str(self.sd)])
        with self.assertRaisesRegex(m.LaunchError,"exactly once"):
            m.build_command(self.exe,self.nro,["{nro}","{nro}"])
        with self.assertRaisesRegex(m.LaunchError,"entire argument"):
            m.build_command(self.exe,self.nro,["{nro}","--input={nro}"])

    def test_missing_emulator_and_invalid_paths_fail_closed(self):
        with self.assertRaisesRegex(m.LaunchError,"existing absolute"):
            m.build_command(self.root/"missing",self.nro,["{nro}"])
        with self.assertRaisesRegex(m.LaunchError,"SD root"):
            m.validate_private_paths(self.root/"nonexistent",self.session,
                                     self.exe,self.nro)
        with self.assertRaisesRegex(m.LaunchError,"timeout"):
            m.launch(self.exe,self.nro,self.sd,self.session,
                     self.args("success"),timeout=0,test_runner=True)
        self.assertFalse(self.session.exists())

    def test_synthetic_fake_runner_cannot_attest_gpu(self):
        report=m.launch(self.exe,self.nro,self.sd,self.session,
                        self.args("success"),timeout=30,test_runner=True)
        self.assertEqual(report["host_process_exit_code"],0)
        self.assertTrue(report["stage231_collected"])
        self.assertTrue(report["stage236_bundle_consistent"])
        self.assertTrue(report["stage241_guest_exit_receipt_accepted"])
        self.assertEqual(report["stage241_guest_exit_receipt"]["guest_exit_code"],0)
        self.assertFalse(report["runtime_gpu_execution_attested"])
        self.assertFalse(report["guest_process_exit_independently_verified"])
        self.assertFalse(report["emulator_gpu_capability_independently_verified"])
        self.assertTrue(report["test_only_runner_declared"])
        private=json.loads((self.session/"stage240_bundle.json").read_text())
        self.assertFalse(private["consistency_gate"]["runtime_gpu_execution_attested"])
        self.assertEqual((self.session/"runtime.log").read_bytes(),
                         (self.session/"host-launch.log").read_bytes())
        self.assertIn(b"NOT_GPU_EVIDENCE",(self.session/"host-launch.log").read_bytes())

    def test_emulator_host_zero_with_valid_pixels_but_no_guest_exit_is_rejected(self):
        report=m.launch(self.exe,self.nro,self.sd,self.session,
                        self.args("success_no_guest"),timeout=30,test_runner=True)
        self.assertEqual(report["host_process_exit_code"],0)
        self.assertTrue(report["stage231_collected"])
        self.assertFalse(report["stage236_bundle_consistent"])
        self.assertFalse(report["stage241_guest_exit_receipt_accepted"])
        bundle=json.loads((self.session/"stage240_bundle.json").read_text())
        self.assertFalse(bundle["consistency_gate"]["stage241_guest_reported_success"])
        self.assertEqual(report["stage241_guest_exit_receipt"]["status"],"missing")
        self.assertFalse(report["runtime_gpu_execution_attested"])

    def test_no_capture_on_successful_process_is_not_a_successful_gpu_run(self):
        report=m.launch(self.exe,self.nro,self.sd,self.session,
                        self.args("incomplete"),timeout=30,test_runner=True)
        self.assertEqual(report["host_process_exit_code"],0)
        self.assertFalse(report["stage231_collected"])
        self.assertFalse(report["stage236_bundle_consistent"])
        self.assertIn("missing",report["stage231_collection_error"])
        self.assertTrue((self.session/"stage240_launch.json").is_file())
        bundle=json.loads((self.session/"stage240_bundle.json").read_text())
        self.assertEqual(bundle["phase"]["phase"],"02_shaders_loaded")

    def test_nonzero_process_exit_is_preserved(self):
        report=m.launch(self.exe,self.nro,self.sd,self.session,
                        self.args("nonzero"),timeout=30,test_runner=True)
        self.assertEqual(report["host_process_exit_code"],7)
        self.assertFalse(report["stage231_collected"])
        self.assertFalse(report["stage236_bundle_consistent"])
        self.assertEqual((self.session/"runner-exit-status.txt").read_text(),"7\n")


    def test_noisy_process_output_is_capped_and_never_collected_as_complete(self):
        report=m.launch(self.exe,self.nro,self.sd,self.session,
                        self.args("noisy"),timeout=30,test_runner=True)
        log=(self.session/"host-launch.log")
        self.assertEqual(report["host_process_exit_code"],0)
        self.assertTrue(report["runner_log_truncated"])
        self.assertEqual(report["runner_log_limit_bytes"],m.MAX_HOST_LOG_BYTES)
        self.assertEqual(report["runner_log_bytes_captured"],m.MAX_HOST_LOG_BYTES)
        self.assertGreater(report["runner_log_bytes_observed"],m.MAX_HOST_LOG_BYTES)
        self.assertEqual(log.stat().st_size,m.MAX_HOST_LOG_BYTES)
        self.assertFalse(report["stage231_collected"])
        self.assertIn("truncated",report["stage231_collection_error"])
        self.assertFalse(report["stage236_bundle_consistent"])
        self.assertFalse(report["runtime_gpu_execution_attested"])


    def test_parent_exit_with_descendant_holding_pipe_triggers_tree_cleanup(self):
        report=m.launch(self.exe,self.nro,self.sd,self.session,
                        self.args("orphan"),timeout=30,test_runner=True)
        self.assertEqual(report["host_process_exit_code"],0)
        self.assertTrue(report["process_tree_cleanup_attempted"])
        self.assertTrue(report["process_tree_cleanup_success"])
        self.assertFalse(report["runner_log_drain_incomplete"])
        self.assertFalse(report["stage231_collected"])
        self.assertIn("process-tree cleanup was required",
                      report["stage231_collection_error"])
        self.assertFalse(report["stage236_bundle_consistent"])
        self.assertFalse(report["runtime_gpu_execution_attested"])
        self.assertEqual(report["process_tree_cleanup_method"],"posix_process_group"
                         if os.name!="nt" else "windows_taskkill_tree")

    def test_no_reuse_of_prepared_session(self):
        m.launch(self.exe,self.nro,self.sd,self.session,
                 self.args("incomplete"),timeout=30,test_runner=True)
        with self.assertRaisesRegex(m.LaunchError,"fresh empty"):
            m.launch(self.exe,self.nro,self.sd,self.session,
                     self.args("success"),timeout=30,test_runner=True)

    def test_no_shell_metacharacter_interpretation(self):
        payload=self.root/"injected.txt"
        args=[str(self.sd),"{nro}","incomplete",f"; touch {payload}"]
        report=m.launch(self.exe,self.nro,self.sd,self.session,
                        args,timeout=30,test_runner=True)
        self.assertFalse(payload.exists())
        self.assertFalse(report["runtime_gpu_execution_attested"])


if __name__=="__main__":
    unittest.main()
