# -*- coding: utf-8 -*-
"""CURIO-003a：event/2 等四个 schema 的夹具校验测试。

证明 schema 既放行全部合格样例，也拦得住全部不合格样例（每条只错在
想要测的那一处，用 JSON Patch 的 replace / add / remove 从合格样例改出）。

运行：在仓库根目录执行
    python -m unittest discover -s tools/tests
"""
import copy
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "tools" / "tests" / "fixtures"

# 夹具文件 -> 对应 schema。不合格样例的 base 也用这个名字选 schema。
SCHEMA_FILES = {
    "events.json": "event.schema.json",
    "receipts.json": "ingest-receipt.schema.json",
    "rewards.json": "reward-entry.schema.json",
    "texts.json": "private-text.schema.json",
}

# 规格 docs/specs/events.md 第 3 节的动词表，逐个对账。
VERBS = [
    "attempt.started", "attempt.completed", "attempt.abandoned",
    "poe.predicted", "poe.explained",
    "sim.adjusted", "sim.observed",
    "item.answered", "hint.used", "answer.revealed", "reflection.written",
    "question.asked", "question.answered",
    "repair.opened", "repair.linked", "repair.practiced", "repair.resolved",
    "plan.created", "plan.task_done", "plan.task_undone",
    "reward.goal_set", "reward.redeem_requested", "reward.spent",
    "reward.adjusted", "reward.revoked",
    "import.voided", "attachment.erased", "text.erased",
]

VERB_COVER_RE = re.compile(r"[a-z0-9][a-z0-9.-]*$")

# 规格第 3 节「谁」一列的 actor.type 允许集，逐动词手写，不从 schema 读。
ACTOR_ALLOWED = {
    "attempt.started": ("learner",),
    "attempt.completed": ("learner",),
    "attempt.abandoned": ("learner", "system"),
    "poe.predicted": ("learner",),
    "poe.explained": ("learner",),
    "sim.adjusted": ("learner",),
    "sim.observed": ("learner",),
    "item.answered": ("learner",),
    "hint.used": ("learner",),
    "answer.revealed": ("learner",),
    "reflection.written": ("learner",),
    "question.asked": ("learner",),
    "question.answered": ("learner", "caregiver"),
    "repair.opened": ("learner", "system"),
    "repair.linked": ("learner", "caregiver", "system"),
    "repair.practiced": ("learner",),
    "repair.resolved": ("learner", "caregiver"),
    "plan.created": ("learner", "caregiver"),
    "plan.task_done": ("learner", "system"),
    "plan.task_undone": ("learner",),
    "reward.goal_set": ("caregiver",),
    "reward.redeem_requested": ("learner",),
    "reward.spent": ("caregiver",),
    "reward.adjusted": ("caregiver",),
    "reward.revoked": ("caregiver",),
    "import.voided": ("caregiver",),
    "attachment.erased": ("caregiver",),
    "text.erased": ("learner", "caregiver"),
}

# 三种 actor.type 对应的 id 前缀。
ACTOR_ID_PREFIX = {"learner": "lrn_", "caregiver": "cg_", "system": "sys:"}

# 规格第 3 节「范围」一列的 attempt_id / content 要求，逐动词手写。
# require_attempt / require_content：True 表示必须有，False 表示必须没有，
# None 表示可有可无（question.asked / repair.opened 的复杂规则另在别处测）。
SCOPE = {
    "attempt.started": dict(attempt=True, content=True),
    "attempt.completed": dict(attempt=True, content=True),
    "attempt.abandoned": dict(attempt=True, content=True),
    "poe.predicted": dict(attempt=True, content=True),
    "poe.explained": dict(attempt=True, content=True),
    "sim.adjusted": dict(attempt=True, content=True),
    "sim.observed": dict(attempt=True, content=True),
    "item.answered": dict(attempt=True, content=True),
    "hint.used": dict(attempt=True, content=True),
    "answer.revealed": dict(attempt=True, content=True),
    "reflection.written": dict(attempt=True, content=True),
    "question.asked": dict(attempt=None, content=None),
    "question.answered": dict(attempt=False, content=False),
    "repair.opened": dict(attempt=None, content=None),
    "repair.linked": dict(attempt=False, content=False),
    "repair.practiced": dict(attempt=False, content=False),
    "repair.resolved": dict(attempt=False, content=False),
    "plan.created": dict(attempt=False, content=False),
    "plan.task_done": dict(attempt=False, content=False),
    "plan.task_undone": dict(attempt=False, content=False),
    "reward.goal_set": dict(attempt=False, content=False),
    "reward.redeem_requested": dict(attempt=False, content=False),
    "reward.spent": dict(attempt=False, content=False),
    "reward.adjusted": dict(attempt=False, content=False),
    "reward.revoked": dict(attempt=False, content=False),
    "import.voided": dict(attempt=False, content=False),
    "attachment.erased": dict(attempt=False, content=False),
    "text.erased": dict(attempt=False, content=False),
}

# 逐动词的合格样例名（对应 valid/events.json 里的 name）。
VERB_VALID_FIXTURE = {
    "attempt.started": "attempt.started",
    "attempt.completed": "attempt.completed",
    "attempt.abandoned": "attempt.abandoned",
    "poe.predicted": "poe.predicted",
    "poe.explained": "poe.explained",
    "sim.adjusted": "sim.adjusted",
    "sim.observed": "sim.observed",
    "item.answered": "item.answered",
    "hint.used": "hint.used",
    "answer.revealed": "answer.revealed",
    "reflection.written": "reflection.written",
    "question.asked": "question.asked",
    "question.answered": "question.answered",
    "repair.opened": "repair.opened-item",
    "repair.linked": "repair.linked",
    "repair.practiced": "repair.practiced",
    "repair.resolved": "repair.resolved",
    "plan.created": "plan.created",
    "plan.task_done": "plan.task_done",
    "plan.task_undone": "plan.task_undone",
    "reward.goal_set": "reward.goal_set",
    "reward.redeem_requested": "reward.redeem_requested",
    "reward.spent": "reward.spent",
    "reward.adjusted": "reward.adjusted",
    "reward.revoked": "reward.revoked",
    "import.voided": "import.voided",
    "attachment.erased": "attachment.erased",
    "text.erased": "text.erased",
}

ALL_ACTOR_TYPES = ("learner", "caregiver", "system")

# 校验后固定的一套合法 id（供替换 actor.id 用）。
FIXED_ACTOR_IDS = {
    "learner": "lrn_01H8ZK6P3M9Q2W5E8R7T4VY0XC",
    "caregiver": "cg_02K9M4P7Q3R5T8V6WY0XCA1BDE",
    "system": "sys:test-shell",
}


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_valid_group(filename):
    """读 valid 夹具，返回 {name: data}。"""
    entries = _load_json(FIXTURE_DIR / "valid" / filename)
    return {entry["name"]: entry["data"] for entry in entries}


def _unescape(token):
    return token.replace("~1", "/").replace("~0", "~")


def _parent_of(document, pointer):
    """解析 JSON Pointer 指向位置的 (父容器, 最后一个 token)。

    前缀不存在或穿过标量时抛 KeyError / IndexError / ValueError。
    """
    if not pointer.startswith("/"):
        raise ValueError("pointer 必须以 / 开头: %r" % pointer)
    tokens = [_unescape(t) for t in pointer.split("/")[1:]]
    if not tokens:
        raise KeyError(pointer)
    parent = document
    for token in tokens[:-1]:
        if isinstance(parent, dict):
            if token not in parent:
                raise KeyError(pointer)
            parent = parent[token]
        elif isinstance(parent, list):
            index = int(token)
            if not 0 <= index < len(parent):
                raise IndexError(pointer)
            parent = parent[index]
        else:
            raise KeyError(pointer)
    return parent, tokens[-1]


def _key_exists(parent, key):
    if isinstance(parent, dict):
        return key in parent
    if isinstance(parent, list):
        return 0 <= key < len(parent)
    return False


def apply_patch(document, patch):
    """就地应用 replace / add / remove 三种操作，返回同一文档。

    replace 和 remove 要求路径原本存在——每一步都真的生效，否则抛
    AssertionError / KeyError / IndexError，让测试失败。
    """
    for op in patch:
        kind = op["op"]
        pointer = op["path"]
        if kind not in ("replace", "add", "remove"):
            raise AssertionError("不支持的操作: %r" % op)
        parent, key = _parent_of(document, pointer)
        if isinstance(parent, list):
            key = int(key)
        if kind in ("replace", "remove"):
            if not _key_exists(parent, key):
                raise KeyError("路径原本不存在，补丁没有生效: %r" % pointer)
        if kind == "replace":
            parent[key] = op["value"]
        elif kind == "remove":
            if isinstance(parent, dict):
                del parent[key]
            else:
                parent.pop(key)
        else:  # add：只往对象里加新键
            if not isinstance(parent, dict):
                raise AssertionError("add 只支持对象目标: %r" % pointer)
            if _key_exists(parent, key):
                raise AssertionError("add 的键已存在，改用 replace: %r" % pointer)
            parent[key] = op["value"]
    return document


class CurioSchemaFixtureTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schemas = {
            name: _load_json(SCHEMA_DIR / name)
            for name in SCHEMA_FILES.values()
        }
        cls.validators = {
            name: Draft202012Validator(schema)
            for name, schema in cls.schemas.items()
        }
        cls.valid = {
            filename: _load_valid_group(filename)
            for filename in SCHEMA_FILES
        }
        cls.invalid = _load_json(FIXTURE_DIR / "invalid" / "events.json")

    # ------------------------------------------------ schema 本身合法

    def test_check_schema(self):
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    # ------------------------------------------------ 合格样例

    def test_valid_fixture_names_unique(self):
        for filename in SCHEMA_FILES:
            entries = _load_json(FIXTURE_DIR / "valid" / filename)
            names = [entry["name"] for entry in entries]
            self.assertEqual(
                len(names), len(set(names)), "%s 里 name 重复" % filename
            )

    def test_valid_fixtures_pass(self):
        for filename, schema_name in SCHEMA_FILES.items():
            validator = self.validators[schema_name]
            for name, data in self.valid[filename].items():
                with self.subTest(fixture="%s#%s" % (filename, name)):
                    validator.validate(data)  # 不过会抛 ValidationError

    def test_every_verb_has_valid_fixture(self):
        names = list(self.valid["events.json"])
        missing = [
            verb for verb in VERBS
            if not any(n == verb or n.startswith(verb + "-") for n in names)
        ]
        self.assertEqual(missing, [], "缺少这些动词的合格样例")

    def test_both_repair_opened_sources_covered(self):
        names = list(self.valid["events.json"])
        for source in ("item", "photo"):
            self.assertTrue(
                any(n.startswith("repair.opened-" + source) for n in names),
                "repair.opened 缺少 %s 来源的合格样例" % source,
            )

    def test_text_erased_orphan_and_lost_covered(self):
        erased = [
            data for name, data in self.valid["events.json"].items()
            if data["verb"] == "text.erased"
        ]
        reasons = {data["payload"]["reason"] for data in erased}
        self.assertIn("orphan", reasons)
        self.assertIn("lost", reasons)

    def test_event_id_unique(self):
        eids = [e["data"]["event_id"] for e in _load_json(FIXTURE_DIR / "valid" / "events.json")]
        self.assertEqual(len(eids), len(set(eids)), "valid/events.json 里 event_id 重复")

    def test_device_seq_unique_per_device(self):
        entries = _load_json(FIXTURE_DIR / "valid" / "events.json")
        pairs = [(e["data"]["device_id"], e["data"]["device_seq"]) for e in entries]
        self.assertEqual(len(pairs), len(set(pairs)), "(device_id, device_seq) 重复")

    # ------------------------------------------------ 按表驱动：谁能发

    def test_actor_types_per_verb(self):
        validator = self.validators["event.schema.json"]
        for verb, allowed in ACTOR_ALLOWED.items():
            base = copy.deepcopy(
                self.valid["events.json"][VERB_VALID_FIXTURE[verb]]
            )
            for atype in ALL_ACTOR_TYPES:
                data = copy.deepcopy(base)
                data["actor"] = {"type": atype, "id": FIXED_ACTOR_IDS[atype]}
                with self.subTest(verb=verb, actor_type=atype):
                    if atype in allowed:
                        validator.validate(data)  # 应通过
                    else:
                        with self.assertRaises(ValidationError):
                            validator.validate(data)

    # ------------------------------------------------ 按表驱动：范围

    def test_scope_per_verb(self):
        validator = self.validators["event.schema.json"]
        # 合法 field 值的来源：item.answered 这条合格样例同时带 attempt_id
        # 和 content，直接取它的值，保证加进去的字段本身合法。
        source = self.valid["events.json"]["item.answered"]
        legal_field = {
            "attempt_id": source["attempt_id"],
            "content": source["content"],
        }
        checked_missing = 0
        checked_present = 0
        for verb, scope in SCOPE.items():
            base = copy.deepcopy(
                self.valid["events.json"][VERB_VALID_FIXTURE[verb]]
            )
            for field, required in (("attempt_id", scope["attempt"]),
                                    ("content", scope["content"])):
                if required is None:
                    continue
                data = copy.deepcopy(base)
                if required is True:
                    data.pop(field, None)  # 必须有却缺了 -> 不通过
                    with self.subTest(verb=verb, field=field, case="missing"):
                        with self.assertRaises(ValidationError):
                            validator.validate(data)
                    checked_missing += 1
                else:  # required is False：不该有却带了 -> 不通过
                    # 先删掉（如果有），再加一个合法值，确保「带了」一定成立。
                    data.pop(field, None)
                    data[field] = copy.deepcopy(legal_field[field])
                    with self.subTest(verb=verb, field=field, case="present"):
                        with self.assertRaises(ValidationError):
                            validator.validate(data)
                    checked_present += 1
        # 防止以后悄悄跳过：实际检查次数必须等于按 SCOPE 表手算的数。
        self.assertEqual(checked_missing, 22, "「必须有却缺了」检查次数不对")
        self.assertEqual(checked_present, 30, "「不该有却带了」检查次数不对")

    # ------------------------------------------------ 按表驱动：多余字段

    def test_payload_extra_field_per_verb(self):
        validator = self.validators["event.schema.json"]
        for verb in VERBS:
            base = copy.deepcopy(
                self.valid["events.json"][VERB_VALID_FIXTURE[verb]]
            )
            base["payload"]["__extra__"] = "规格里没有的键"
            with self.subTest(verb=verb):
                with self.assertRaises(ValidationError):
                    validator.validate(base)

    # ------------------------------------------------ 不合格样例

    def test_invalid_fixture_names_unique_and_wellformed(self):
        names = [case["name"] for case in self.invalid]
        self.assertEqual(len(names), len(set(names)), "不合格样例 name 重复")
        for name in names:
            self.assertTrue(
                VERB_COVER_RE.fullmatch(name), "name 格式不对: %r" % name
            )

    def test_invalid_fixtures_rejected(self):
        for case in self.invalid:
            with self.subTest(case=case["name"]):
                base_file, _, base_name = case["base"].partition("#")
                self.assertIn(
                    base_file, SCHEMA_FILES, "base 指向未知文件: %r" % case["base"]
                )
                self.assertIn(
                    base_name, self.valid[base_file],
                    "base 指向不存在的合格样例: %r" % case["base"],
                )
                data = copy.deepcopy(self.valid[base_file][base_name])
                try:
                    apply_patch(data, case["patch"])
                except (KeyError, IndexError, ValueError, AssertionError) as exc:
                    self.fail("补丁没有完全生效: %s（%r）" % (exc, case))
                validator = self.validators[SCHEMA_FILES[base_file]]
                with self.assertRaises(ValidationError):
                    validator.validate(data)

    def test_every_verb_has_invalid_fixture(self):
        bases = [case["base"] for case in self.invalid]
        missing = [
            verb for verb in VERBS
            if not any(
                b.startswith("events.json#")
                and (b == "events.json#" + verb
                     or b.startswith("events.json#" + verb + "-"))
                for b in bases
            )
        ]
        self.assertEqual(missing, [], "缺少这些动词的不合格样例")


if __name__ == "__main__":
    unittest.main()

# END OF FILE
