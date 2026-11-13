"""tools/recover_key.py 的正反测试（docs/specs/backup.md 第 12 节，原则 8）。

为了快：样例文件用读的程序接受的最低轮数 100000（写的程序 v1 固定 600000），搜索范围只给几十个数。
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import backup_ref as B  # noqa: E402
import recover_key as R  # noqa: E402

SCRIPT = REPO / "tools" / "recover_key.py"
DOC = (b'{"schema":"backup-manifest/1","created_at":"2026-11-13T10:30:00.000Z","learner_id":"lrn_01JC4Y00000000000000000001",'
       b'"device_id":"dev_01JC4Y00000000000000000002","app_commit":"0000000","counts":{"inbox":0,"receipt":0,"import":0,"archive":0,"release":0}}\n')


def make_file(digits, iterations=100000):
    import hashlib
    doc = DOC + B.line({"t": "end", "lines": 1, "sha256": hashlib.sha256(DOC).hexdigest()})
    return B.encode_backup(doc, digits=digits, created_at="2026-11-13T10:30:00.000Z", salt=bytes(range(16)),
                           nonce_prefix=bytes(7), iterations=iterations, chunk_size=64, compression="none")


class RecoverKey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "mine.curio"
        cls.file = make_file("000017")
        cls.path.write_bytes(cls.file)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_file_is_a_real_backup(self):
        d = B.decode_backup(self.file, "000017")
        self.assertTrue(d["ok"], d)

    def test_same_derivation_as_backup_ref(self):
        salt, check, it = R.read_header(self.file)
        self.assertEqual(R.key_check("000017", salt, it), check)
        self.assertNotEqual(R.key_check("000018", salt, it), check)
        self.assertEqual(B._KEYS, {}, "不留缓存")

    def test_found_single_process(self):
        self.assertEqual(R.search(self.file, 10, 20, jobs=1), "000017")

    def test_found_multi_process(self):
        self.assertEqual(R.search(self.file, 0, 40, jobs=2), "000017")

    def test_not_in_range(self):
        self.assertIsNone(R.search(self.file, 0, 9, jobs=1))

    def test_not_curio(self):
        with self.assertRaises(B.Fail) as c:
            R.search(b"\x89PNG\r\n\x1a\n" + bytes(100), 0, 5, jobs=1)
        self.assertEqual(c.exception.code, "not_curio")

    def test_bad_range(self):
        with self.assertRaises(ValueError):
            R.search(self.file, 5, 1, jobs=1)

    def test_cli(self):
        ok = subprocess.run([sys.executable, str(SCRIPT), str(self.path), "--from", "15", "--to", "19", "--jobs", "1", "--quiet"],
                            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("000 017", ok.stdout)
        miss = subprocess.run([sys.executable, str(SCRIPT), str(self.path), "--from", "20", "--to", "22", "--jobs", "1", "--quiet"],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(miss.returncode, 1)
        self.assertEqual(miss.stdout, "")
        png = Path(self.tmp.name) / "photo.curio"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(100))
        bad = subprocess.run([sys.executable, str(SCRIPT), str(png), "--quiet"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(bad.returncode, 2)
        self.assertIn(B.MESSAGES["not_curio"], bad.stderr)


if __name__ == "__main__":
    unittest.main()
