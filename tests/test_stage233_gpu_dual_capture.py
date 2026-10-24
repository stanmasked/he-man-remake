"""Stage233 tests use invented byte buffers. They are NOT GPU runtime proof."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage233_validate_gpu_dual_capture as m
from stage231_capture_session import payload

NRO=bytes(16)+b"NRO0"+b"this-is-a-fake-test-binary"
HASH=hashlib.sha256(NRO).hexdigest()
NONCE="f"*32
RECEIPT=("STAGE230_GPU_READBACK width=16 height=8 bytes=512 pixels=128 "
         f"mismatches=0 nonce={NONCE}\n")
SESSION={"schema":"stage231-capture-session-v1","nonce":NONCE,"nro_sha256":HASH}
COLLECTED={"schema":"stage231-collected-synthetic-gpu-evidence-v1",
           "result":"submitted_capture_matches_challenge_and_pixels",
           "nonce":NONCE,"nro_sha256":HASH,
           "rgba_sha256":hashlib.sha256(payload()).hexdigest(),
           "runtime_provenance_attested":False}


class Stage233Tests(unittest.TestCase):
    def valid(self,upload=None,render=None,session=None,collected=None,
              receipt=None,digest=None):
        return m.verify(payload() if upload is None else upload,
                        payload() if render is None else render,
                        SESSION if session is None else session,
                        COLLECTED if collected is None else collected,
                        RECEIPT if receipt is None else receipt,
                        HASH if digest is None else digest)

    def test_positive_fixture_is_not_gpu_proof(self):
        result=self.valid()
        self.assertEqual(result["upload_pixels"],128)
        self.assertEqual(result["render_pixels"],128)
        self.assertFalse(result["runtime_gpu_execution_attested"])

    def test_damaged_upload_rejected_independent_of_render(self):
        bad=bytearray(payload())
        bad[22]^=1
        with self.assertRaisesRegex(m.RoundtripError,"upload mismatch"):
            self.valid(upload=bytes(bad))

    def test_damaged_render_rejected_independent_of_upload(self):
        bad=bytearray(payload())
        bad[400]=1
        with self.assertRaisesRegex(m.RoundtripError,"render mismatch"):
            self.valid(render=bytes(bad))

    def test_truncation_and_overflow_both_paths(self):
        for b in (payload()[:-1],payload()+b"x",b""):
            with self.subTest(size=len(b)):
                with self.assertRaises(m.RoundtripError):
                    self.valid(upload=b)
                with self.assertRaises(m.RoundtripError):
                    self.valid(render=b)

    def test_nonce_and_run_integrity(self):
        for args in [
            {"receipt":RECEIPT.replace(NONCE,"0"*32)},
            {"session":dict(SESSION,nro_sha256="0"*64)},
            {"collected":dict(COLLECTED,nonce="0"*32)},
            {"collected":dict(COLLECTED,rgba_sha256="0"*64)},
            {"collected":dict(COLLECTED,runtime_provenance_attested=True)},
            {"digest":"0"*64},
        ]:
            with self.subTest(args=args),self.assertRaises(m.RoundtripError):
                self.valid(**args)

    def test_missing_completed_session(self):
        with self.assertRaises(m.RoundtripError):
            self.valid(collected={})
        with self.assertRaises(m.RoundtripError):
            self.valid(session={})

    def test_private_collection_requires_both_files(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            sd=root/"sd"/"switch"/"heman-stage230"
            sd.mkdir(parents=True)
            out=root/"private"
            out.mkdir()
            nro=root/"fake.nro"
            nro.write_bytes(NRO)
            (out/"stage231_session.json").write_text(json.dumps(SESSION))
            (out/"stage231_collected.json").write_text(json.dumps(COLLECTED))
            (out/"readback.receipt").write_text(RECEIPT)
            (out/"readback.rgba").write_bytes(payload())
            with self.assertRaisesRegex(m.RoundtripError,"upload readback missing"):
                m.collect(nro,root/"sd",out)
            (sd/"upload.rgba").write_bytes(payload())
            report=m.collect(nro,root/"sd",out)
            self.assertFalse(report["runtime_gpu_execution_attested"])
            self.assertEqual((out/"upload.rgba").read_bytes(),payload())
            with self.assertRaisesRegex(m.RoundtripError,"already collected"):
                m.collect(nro,root/"sd",out)

    def test_stale_upload_is_rejected_by_byte_mismatch(self):
        with self.assertRaisesRegex(m.RoundtripError,"upload mismatch"):
            self.valid(upload=bytes([0xA5])*512)


if __name__=="__main__":
    unittest.main()
