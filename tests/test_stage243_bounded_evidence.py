"""Stage243 bounded evidence tests use temporary files, never game captures."""
from pathlib import Path
import os
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from stage243_bounded_evidence import (
    read_limited,EvidenceReadError,MAX_LOG_BYTES,MAX_RGBA_BYTES,
)


class BoundedEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="heman-stage243-fake-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.path=self.root/"fake-capture.rgba"

    def test_exact_512_bytes_read_succeeds(self):
        data=bytes(range(256))*2
        self.path.write_bytes(data)
        self.assertEqual(read_limited(self.path,MAX_RGBA_BYTES,"pixels"),data)

    def test_sparse_513_byte_rgba_is_rejected(self):
        with self.path.open("wb") as stream:
            stream.truncate(MAX_RGBA_BYTES+1)
        with self.assertRaisesRegex(EvidenceReadError,"oversized"):
            read_limited(self.path,MAX_RGBA_BYTES,"pixels")

    def test_sparse_four_megabyte_log_is_rejected(self):
        with self.path.open("wb") as stream:
            stream.truncate(MAX_LOG_BYTES+1)
        with self.assertRaisesRegex(EvidenceReadError,"oversized"):
            read_limited(self.path,MAX_LOG_BYTES,"fake log")

    def test_missing_and_directory_paths_fail(self):
        with self.assertRaisesRegex(EvidenceReadError,"missing file"):
            read_limited(self.path,512,"missing")
        with self.assertRaisesRegex(EvidenceReadError,"regular file"):
            read_limited(self.root,512,"directory")

    def test_symlink_is_not_followed_on_supported_platforms(self):
        target=self.root/"target"
        target.write_bytes(b"untouched")
        self.path.symlink_to(target)
        if getattr(os,"O_NOFOLLOW",0):
            with self.assertRaises(EvidenceReadError):
                read_limited(self.path,512,"symlink")
        self.assertEqual(target.read_bytes(),b"untouched")

    def test_invalid_limits_fail(self):
        self.path.write_bytes(b"ok")
        for limit in (0,-1,MAX_LOG_BYTES+1,1.5):
            with self.subTest(limit=limit),self.assertRaises(EvidenceReadError):
                read_limited(self.path,limit,"invalid")


if __name__=="__main__":
    unittest.main()
