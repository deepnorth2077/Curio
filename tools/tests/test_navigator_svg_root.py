"""领航员 SVG：根必须是 SVG 命名空间的 <svg>，不许嵌套 <svg>（PR #244 审查建议 1、2）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_checks  # noqa: E402
from nav_fixtures import face_svg  # noqa: E402


class TestNavigatorSvgRoot(unittest.TestCase):
    def errors(self, text):
        return ci_checks.check_navigator_svg(text.encode("utf-8") if isinstance(text, str) else text)

    def test_plain_face_passes(self):
        self.assertEqual(self.errors(face_svg()), [])

    def test_nested_svg_fails(self):
        self.assertTrue(self.errors(face_svg(inject='<svg viewBox="0 0 48 48"></svg>')))

    def test_root_in_other_namespace_fails(self):
        good = face_svg()
        text = good.decode("utf-8") if isinstance(good, bytes) else good
        bad = text.replace('xmlns="http://www.w3.org/2000/svg"', 'xmlns="urn:x"', 1)
        self.assertNotEqual(bad, text)
        self.assertTrue(self.errors(bad))


if __name__ == "__main__":
    unittest.main()
