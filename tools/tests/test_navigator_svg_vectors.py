"""领航员 SVG 的检查向量（app/vectors/navigator-svg.json）：Python 的 check_navigator_svg 和外壳的 JS 版用同一份，结果都要和 ok 一致。"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import ci_checks  # noqa: E402

VECTORS = json.loads((ROOT / "app/vectors/navigator-svg.json").read_text(encoding="utf-8"))


class TestNavigatorSvgVectors(unittest.TestCase):
    def test_has_both_kinds(self):
        oks = [c for c in VECTORS["checks"] if c["ok"]]
        self.assertGreaterEqual(len(oks), 5)
        self.assertGreaterEqual(len(VECTORS["checks"]) - len(oks), 30)

    def test_every_vector(self):
        for case in VECTORS["checks"]:
            with self.subTest(case["name"]):
                errors = ci_checks.check_navigator_svg(case["svg"].encode("utf-8"))
                self.assertEqual(not errors, case["ok"], errors)

    def test_repository_faces_pass(self):
        for d in sorted((ROOT / "content/navigators").iterdir()):
            for face in ci_checks.NAVIGATOR_FACES:
                with self.subTest(f"{d.name}/{face}"):
                    self.assertEqual(ci_checks.check_navigator_svg((d / f"{face}.svg").read_bytes()), [])


if __name__ == "__main__":
    unittest.main()
