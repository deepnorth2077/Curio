"""ci_checks.py 对 content/navigators/ 的检查（docs/specs/navigators.md 第 1 节、「内容检查的反例」，#242 PR 1）。
验收测试的作者写，实现者不改（受保护路径）。

只通过 ci_checks.run（和 CI 一样的入口）观察结果，不假定内部函数名。规格没有规定报错文字，所以反例只断言：
有一条错误落在 content/navigators/ 下的文件，或文字里提到「领航员」。通过样例要求整个检查零错误。
每条反例都只错一处，其余部分和通过样例一样（AGENTS.md 原则 8：每条规则一个通过样例、一个失败样例）。
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from nav_fixtures import FACES, LAMP, RING, face_svg, nav_files, navigator_yaml, two_navigators  # noqa: E402
from test_ci_checks import Base  # noqa: E402

BRANCH = "arch/navigators"


def nav_errors(result):
    return [(f, m) for f, m in result.errors if (f or "").startswith("content/navigators") or "领航员" in m]


class NavBase(Base):
    def setUp(self):
        super().setUp()
        # 领航员 yaml 的 author.prompt_ref 指向设计说明；放一份，免得「文件不存在」干扰
        self.r.write("prototype/design/navigator.html", "<html></html>\n")

    def put(self, files):
        for path, text in files.items():
            self.r.write(path, text)

    def main_with_two(self):
        self.put(two_navigators())
        self.r.baseline()
        self.r.branch(BRANCH)

    def fresh_branch(self):
        self.r.baseline()
        self.r.branch(BRANCH)

    def add(self, spec, dir=None, **kw):
        """dir：写进哪个目录（默认等于 id；造「目录名和 id 不同」的反例时才给）。"""
        for name, text in nav_files(**{**spec, **kw}).items():
            self.r.write(f"content/navigators/{dir or kw.get('nid') or spec['nid']}/{name}", text)

    def assert_rejected(self, why):
        self.r.commit()
        errs = nav_errors(self.r.check())
        self.assertTrue(errs, f"本应报错：{why}")

    def with_ring_face(self, face, text):
        """小灯合法，小环有一张脸被换成 text（或整套有别的错）。"""
        self.fresh_branch()
        self.add(LAMP)
        self.add(RING, faces={face: text})


class TestPassing(NavBase):
    def test_two_valid_navigators_pass(self):
        self.fresh_branch()
        self.put(two_navigators())
        self.r.commit()
        result = self.r.check()
        self.ok(result)
        self.assertEqual(nav_errors(result), [])

    def test_limits_are_inclusive_16_elements_one_accent_3072_bytes_6_chars_40_chars(self):
        self.fresh_branch()
        self.add(LAMP)
        edge = face_svg(seed=1, count=16, accent=1, pad_to=3072)
        self.add(RING, title="小环小环小环", intro="我" * 40, faces={"curious": edge})
        self.r.commit()
        self.ok(self.r.check())

    def test_ordinary_revision_of_a_merged_navigator_passes(self):
        """改画法、名字、见面的话是普通改版：version 加一，id 和 unlock 不动。"""
        self.main_with_two()
        self.add(LAMP, title="小灯灯", intro="新的一句见面的话。", version=2, faces={"clap": face_svg(seed=9, count=6)})
        self.r.commit()
        self.ok(self.r.check())

    def test_adding_a_third_navigator_is_only_adding_content(self):
        self.main_with_two()
        self.add(dict(nid="nav.moon", title="小月", intro="我喜欢在夜里发亮。", seed=5))
        self.r.commit()
        self.ok(self.r.check())


class TestSvgRules(NavBase):
    def test_title_element_rejected(self):
        self.with_ring_face("curious", face_svg(inject="<title>脸</title>"))
        self.assert_rejected("带 title")

    def test_desc_element_rejected(self):
        self.with_ring_face("curious", face_svg(inject="<desc>脸</desc>"))
        self.assert_rejected("带 desc")

    def test_comment_rejected(self):
        self.with_ring_face("think", face_svg(inject="<!-- 草稿 -->"))
        self.assert_rejected("带注释")

    def test_cdata_rejected(self):
        self.with_ring_face("think", face_svg(inject="<![CDATA[x]]>"))
        self.assert_rejected("带 CDATA")

    def test_viewbox_100_rejected(self):
        self.with_ring_face("wrong", face_svg(viewbox="0 0 100 100"))
        self.assert_rejected("viewBox 不是 0 0 48 48")

    def test_text_element_rejected(self):
        self.with_ring_face("clap", face_svg(inject='<text x="2" y="4" class="f-ink">好</text>'))
        self.assert_rejected("用了 text")

    def test_unknown_class_f_red_rejected(self):
        self.with_ring_face("clap", face_svg(inject='<circle class="f-red" cx="5" cy="5" r="2"/>'))
        self.assert_rejected("类 f-red 不在十个里")

    def test_class_on_g_rejected(self):
        self.with_ring_face("surprised", face_svg(inject='<g class="k"><circle class="f-ink" cx="5" cy="5" r="2"/></g>'))
        self.assert_rejected("类写在 g 上")

    def test_fill_attribute_color_rejected(self):
        self.with_ring_face("waiting", face_svg(inject='<circle fill="#000" cx="5" cy="5" r="2"/>'))
        self.assert_rejected('fill="#000"')

    def test_stroke_attribute_color_rejected(self):
        self.with_ring_face("waiting", face_svg(inject='<path stroke="red" d="M1 1L5 5"/>'))
        self.assert_rejected('stroke="red"')

    def test_17_drawable_elements_rejected(self):
        self.with_ring_face("curious", face_svg(count=17))
        self.assert_rejected("17 个能画出东西的元素")

    def test_two_f_accent_elements_rejected(self):
        self.with_ring_face("curious", face_svg(count=5, accent=2))
        self.assert_rejected("两个 f-accent")

    def test_id_attribute_rejected(self):
        self.with_ring_face("curious", face_svg(inject='<circle id="a" class="f-ink" cx="5" cy="5" r="2"/>'))
        self.assert_rejected("带 id 属性")

    def test_over_3_kib_rejected(self):
        self.with_ring_face("curious", face_svg(pad_to=3073))
        self.assert_rejected("超过 3 KiB")

    def test_use_defs_gradient_clippath_rejected(self):
        for name, extra in {
            "use": '<use href="#a"/>',
            "defs": "<defs></defs>",
            "gradient": '<linearGradient x1="0" y1="0" x2="1" y2="1"/>',
            "clipPath": "<clipPath></clipPath>",
        }.items():
            with self.subTest(element=name):
                self.setUp_again()
                self.with_ring_face("curious", face_svg(inject=extra))
                self.assert_rejected(name)

    def setUp_again(self):
        self.r.close()
        self.r = type(self.r)()
        self.r.write("prototype/design/navigator.html", "<html></html>\n")


class TestYamlAndTree(NavBase):
    def test_missing_wrong_svg_rejected(self):
        self.fresh_branch()
        self.add(LAMP)
        self.add(RING, omit=("wrong.svg",))
        self.assert_rejected("缺 wrong.svg")

    def test_every_face_file_is_required(self):
        for face in FACES:
            with self.subTest(face=face):
                self.r.close()
                self.r = type(self.r)()
                self.r.write("prototype/design/navigator.html", "<html></html>\n")
                self.fresh_branch()
                self.add(LAMP)
                self.add(RING, omit=(face + ".svg",))
                self.assert_rejected(f"缺 {face}.svg")

    def test_unlock_lit_rejected(self):
        self.fresh_branch()
        self.add(LAMP)
        self.add(RING, unlock={"lit": ["math.number.fraction-intro"]})
        self.assert_rejected("unlock 写成 lit")

    def test_directory_name_must_equal_id(self):
        self.fresh_branch()
        self.add(LAMP)
        self.add(RING, dir="nav.ring", nid="nav.rng")
        self.assert_rejected("目录名 nav.ring，id 是 nav.rng")

    def test_title_over_6_chars_rejected(self):
        self.fresh_branch()
        self.add(LAMP)
        self.add(RING, title="小环小环小环小")
        self.assert_rejected("title 7 个字")

    def test_intro_over_40_chars_rejected(self):
        self.fresh_branch()
        self.add(LAMP)
        self.add(RING, intro="我" * 41)
        self.assert_rejected("intro 41 个字")

    def test_unknown_review_value_rejected(self):
        self.fresh_branch()
        self.add(LAMP)
        self.add(RING, review="done")
        self.assert_rejected("review 不在 pending/claude-reviewed/approved 里")

    def test_no_start_true_anywhere_rejected(self):
        self.fresh_branch()
        self.add(LAMP, unlock={"start": False})
        self.add(RING, unlock={"start": False})
        self.assert_rejected("整个目录里没有 start: true")


class TestAgainstMain(NavBase):
    def test_changing_unlock_of_a_merged_navigator_rejected(self):
        self.main_with_two()
        self.add(RING, unlock={"start": False}, version=2)
        self.assert_rejected("改了已进 main 的 unlock")

    def test_removing_unlock_of_a_merged_navigator_rejected(self):
        self.main_with_two()
        text = navigator_yaml("nav.ring", "小环", RING["intro"]).replace("unlock:\n  start: true\n", "")
        self.assertNotIn("unlock", text)
        self.r.write("content/navigators/nav.ring/navigator.yaml", text)
        self.assert_rejected("去掉了已进 main 的 unlock")

    def test_deleting_a_merged_navigator_rejected(self):
        self.main_with_two()
        for name in ["navigator.yaml"] + [f + ".svg" for f in FACES]:
            self.r.delete(f"content/navigators/nav.ring/{name}")
        self.assert_rejected("删掉了已进 main 的 nav.ring（nav.lamp 还在）")

    def test_deleting_only_the_yaml_of_a_merged_navigator_rejected(self):
        self.main_with_two()
        self.r.delete("content/navigators/nav.ring/navigator.yaml")
        self.assert_rejected("只删了 navigator.yaml")

    def test_changing_the_id_of_a_merged_navigator_rejected(self):
        self.main_with_two()
        self.r.write("content/navigators/nav.ring/navigator.yaml", navigator_yaml("nav.ringx", "小环", RING["intro"]))
        self.assert_rejected("改了已进 main 的 id")


if __name__ == "__main__":
    unittest.main()
