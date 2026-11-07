"""黄金向量自身的检查（切片规格 docs/specs/slice-1.md 第 7 节）。

向量里的期望值是 Claude 按规格手算的。这个文件做两件事：
1. 检查向量的格式，以及标成「接收」「重复」的事件确实能通过 schemas/event.schema.json；
2. 用一份按规格独立写的 Python 对照实现，复核每个手算的期望值。两边对不上，说明向量或对照实现有错，要查清楚，
   不能直接把对照实现的结果抄进向量。

对照实现不是被测代码（被测的是浏览器内核 kernel/js 和引擎 engine/js），也不交给实现 AI。
"""
import json
import math
import random
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
KERNEL_VECTORS = REPO / "kernel/vectors"
GRADING = REPO / "engine/vectors/grading.json"
EVENT_SCHEMA = json.loads((REPO / "schemas/event.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(EVENT_SCHEMA)
SLICE_VERBS = {"attempt.started", "item.answered", "hint.used", "attempt.completed", "attempt.abandoned"}
EXPECTS = {"accepted", "duplicate", "quarantined:invalid", "quarantined:conflict"}
MAX_SAFE = 2**53 - 1


# ---------------------------------------------------------------- 对照实现：摄入
def _reject_constant(name):
    raise ValueError(f"{name} 不是合法 JSON")


def _numbers(value):
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _numbers(item)
    elif isinstance(value, list):
        for item in value:
            yield from _numbers(item)


def _number_ok(x):
    x = float(x)
    if math.isnan(x) or math.isinf(x):
        return False
    if x == int(x):
        return abs(x) <= MAX_SAFE
    if abs(x) >= 1e9:
        return False
    text = repr(x)
    mantissa, _, exponent = text.partition("e")
    decimals = len(mantissa.partition(".")[2])
    if exponent:
        decimals -= int(exponent)
    return decimals <= 6


def same(a, b):
    """语义相同（事件规格 5.2）：类型必须相同，true 和 1 不同；数字按数值比。"""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


class RefLog:
    def __init__(self):
        self.by_id, self.by_seq, self.accepted, self.raws = {}, {}, [], []

    def ingest(self, raw):
        if len(raw.encode("utf-8")) > 16384:
            return "quarantined:invalid"
        try:
            event = json.loads(raw, parse_constant=_reject_constant)
        except ValueError:
            return "quarantined:invalid"
        if not isinstance(event, dict):
            return "quarantined:invalid"
        if not all(_number_ok(x) for x in _numbers(event)):
            return "quarantined:invalid"
        if not VALIDATOR.is_valid(event) or event["verb"] not in SLICE_VERBS:
            return "quarantined:invalid"
        old = self.by_id.get(event["event_id"])
        if old is not None:
            return "duplicate" if same(old, event) else "quarantined:conflict"
        if (event["device_id"], event["device_seq"]) in self.by_seq:
            return "quarantined:conflict"
        self.by_id[event["event_id"]] = event
        self.by_seq[(event["device_id"], event["device_seq"])] = event["event_id"]
        self.accepted.append(event)
        self.raws.append(raw)
        return "accepted"


# ---------------------------------------------------------------- 对照实现：掌握度
END = {"attempt.completed", "attempt.abandoned"}


# 下面几个开关只给「向量能不能区分错误算法」的测试用（TestVectorsCatchWrongAlgorithms），默认值就是规格的写法
VARIANT = {"sort": "device_seq", "pick": "min", "best": "ratio", "zero_best": True}


def _order(events):
    if VARIANT["sort"] == "device_seq":
        return sorted(events, key=lambda e: e["device_seq"])
    return sorted(events, key=lambda e: e[VARIANT["sort"]])


def violated_rule(events):
    if VARIANT["pick"] == "max":
        broken = [r for r in range(1, 6) if _check_rule(events, r)]
        return broken[-1] if broken else None
    for rule in range(1, 6):
        if _check_rule(events, rule):
            return rule
    return None


def _check_rule(events, rule):
    """这次尝试是否违反第 rule 条（事件规格 6.3）。"""
    evs = _order(events)
    if rule == 1:
        return len({e["device_id"] for e in evs}) > 1 or len({e["learner_id"] for e in evs}) > 1
    if rule == 2:
        for e in evs:
            actor = e["actor"]
            if not (actor["type"] == "learner" and actor["id"] == e["learner_id"]):
                if not (e["verb"] == "attempt.abandoned" and actor["type"] == "system"):
                    return True
        return False
    if rule == 3:
        return any(not same(e["content"], evs[0]["content"]) for e in evs)
    if rule == 4:
        starts = [i for i, e in enumerate(evs) if e["verb"] == "attempt.started"]
        ends = [i for i, e in enumerate(evs) if e["verb"] in END]
        return starts != [0] or len(ends) > 1 or bool(ends and ends[0] != len(evs) - 1)
    tries = {}
    for e in evs:
        if e["verb"] == "item.answered":
            tries.setdefault(e["payload"]["item_id"], []).append(e["payload"]["try"])
    return any([float(t) for t in seq] != [float(i) for i in range(1, len(seq) + 1)] for seq in tries.values())


def ref_mastery(events):
    attempts = {}
    for e in events:
        attempts.setdefault(e["attempt_id"], []).append(e)
    nodes = {e["content"]["node_id"]: {"explored": False, "best": None} for e in events if "content" in e}
    conflicts = []
    for attempt_id, evs in attempts.items():
        rule = violated_rule(evs)
        if rule is not None:
            conflicts.append({"attempt_id": attempt_id, "rule": rule})
            continue
        evs = _order(evs)
        if evs[-1]["verb"] != "attempt.completed":
            continue
        node = nodes[evs[0]["content"]["node_id"]]
        node["explored"] = True
        if evs[0]["content"]["activity_kind"] != "quiz":
            continue
        answered = {e["payload"]["item_id"] for e in evs if e["verb"] == "item.answered"}
        correct = {e["payload"]["item_id"] for e in evs
                   if e["verb"] == "item.answered" and float(e["payload"]["try"]) == 1 and e["payload"]["correct"] is True}
        if not answered or (not VARIANT["zero_best"] and not correct):
            continue
        cand = (len(correct), len(answered))
        best = node["best"]
        if VARIANT["best"] == "count":
            better = best is None or cand > best
        elif VARIANT["best"] == "tie-keep-last":
            better = best is None or cand[0] * best[1] >= best[0] * cand[1]
        else:
            better = best is None or cand[0] * best[1] > best[0] * cand[1] or (cand[0] * best[1] == best[0] * cand[1] and cand[1] > best[1])
        if better:
            node["best"] = cand
    out = {}
    for node_id, n in nodes.items():
        best = n["best"]
        if best is not None and best[0] * 5 >= best[1] * 4:
            state = "lit"
        elif n["explored"]:
            state = "explored"
        else:
            state = "untouched"
        out[node_id] = {"state": state, "best": None if best is None else {"correct": best[0], "answered": best[1]}}
    return {"algorithm_version": "mastery/1", "nodes": out, "conflicts": sorted(conflicts, key=lambda c: c["attempt_id"])}


# ---------------------------------------------------------------- 对照实现：判分
FULLWIDTH = str.maketrans("０１２３４５６７８９／．", "0123456789/.")
NUMBER = re.compile(r"-?[0-9]+(\.[0-9]+)?")
FRACTION_SLASH = re.compile(r"([0-9]{1,6}) */ *([0-9]{1,6})")
FRACTION_ZH = re.compile(r"([0-9]{1,6}) *分之 *([0-9]{1,6})")


SPACES = "\t\n\x0b\x0c\r \u3000"   # 切片规格第 5 节：只去这 7 种，不用 str.strip() 的默认集合


def ref_grade(answer, response):
    r = response.strip(SPACES).translate(FULLWIDTH)
    kind = answer["type"]
    if kind == "choice":
        for choice in answer["choices"]:
            if choice["id"] == r:
                return (True, None) if choice.get("correct") else (False, choice.get("misconception"))
        return False, None
    if kind == "number":
        if not NUMBER.fullmatch(r):
            return False, None
        x, tol = float(r), answer.get("tolerance", 0)
        if abs(x - answer["value"]) <= tol:
            return True, None
        for cw in answer.get("common_wrong", []):
            if abs(x - cw["value"]) <= tol:
                return False, cw["misconception"]
        return False, None
    m = FRACTION_SLASH.fullmatch(r)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
    else:
        m = FRACTION_ZH.fullmatch(r)
        if not m:
            return False, None
        b, a = int(m.group(1)), int(m.group(2))
    if b == 0:
        return False, None
    eq = answer.get("accept_equivalent", False)

    def match(n, d):
        return a * d == n * b if eq else (a == n and b == d)
    if match(answer["numerator"], answer["denominator"]):
        return True, None
    for cw in answer.get("common_wrong", []):
        if match(cw["numerator"], cw["denominator"]):
            return False, cw["misconception"]
    return False, None


# ---------------------------------------------------------------- 测试
def raw_of(vector, item):
    if "raw" in item:
        raw = item["raw"]
        if "pad_to_bytes" in item:
            raw += " " * (item["pad_to_bytes"] - len(raw.encode("utf-8")))
            assert len(raw.encode("utf-8")) == item["pad_to_bytes"]
        return raw
    return json.dumps(dict(vector["base"], **item["event"]), ensure_ascii=False)


NUMBERS = KERNEL_VECTORS / "numbers.json"


def vectors():
    """摄入和掌握度向量。numbers.json 格式不同，单独测。"""
    return [(p.name, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(KERNEL_VECTORS.glob("*.json")) if p != NUMBERS]


def run(v):
    """按执行器的规则跑一遍（切片规格第 7 节）：逐项摄入；有 mastery_after 的项当场投影。"""
    log, results, checkpoints = RefLog(), [], []
    for item in v["inputs"]:
        results.append(log.ingest(raw_of(v, item)))
        if "mastery_after" in item:
            checkpoints.append((item["mastery_after"], ref_mastery(log.accepted)))
    return log, results, checkpoints


class TestKernelVectors(unittest.TestCase):
    def test_vectors_exist(self):
        self.assertGreaterEqual(len(vectors()), 8)

    def test_format(self):
        for name, v in vectors():
            with self.subTest(vector=name):
                self.assertEqual(set(v), {"name", "about", "order_free", "base", "inputs", "mastery", "worked"})
                self.assertEqual(v["name"] + ".json", name)
                self.assertTrue(v["worked"].strip())
                for item in v["inputs"]:
                    self.assertIn(item["expect"], EXPECTS)
                    self.assertEqual(len({"event", "raw"} & set(item)), 1)
                    self.assertTrue(set(item) <= {"event", "raw", "pad_to_bytes", "expect", "why", "mastery_after"})
                    if "pad_to_bytes" in item:
                        self.assertIn("raw", item)
                    if item["expect"].startswith("quarantined") or "raw" in item:
                        self.assertTrue(item.get("why"), "隔离和原始文字的输入要写 why")

    def test_accepted_and_duplicate_inputs_pass_the_event_schema(self):
        for name, v in vectors():
            for i, item in enumerate(v["inputs"]):
                if item["expect"] in ("accepted", "duplicate"):
                    with self.subTest(vector=name, input=i):
                        event = json.loads(raw_of(v, item))
                        errors = [e.message for e in VALIDATOR.iter_errors(event)]
                        self.assertEqual(errors, [])

    def test_hand_written_ingest_results_match_reference(self):
        for name, v in vectors():
            log = RefLog()
            for i, item in enumerate(v["inputs"]):
                with self.subTest(vector=name, input=i):
                    self.assertEqual(log.ingest(raw_of(v, item)), item["expect"], item.get("why", ""))

    def test_hand_written_mastery_matches_reference(self):
        for name, v in vectors():
            log, _, checkpoints = run(v)
            with self.subTest(vector=name):
                self.assertEqual(ref_mastery(log.accepted), v["mastery"])
                for i, (expected, actual) in enumerate(checkpoints):
                    with self.subTest(checkpoint=i):
                        self.assertEqual(actual, expected)

    def test_log_keeps_exactly_the_first_accepted_raw_texts(self):
        """执行器的通用断言：log.raw() 正好是标成 accepted 的原始文字，按顺序；重复和冲突不替换原文。"""
        for name, v in vectors():
            log, _, _ = run(v)
            with self.subTest(vector=name):
                self.assertEqual(log.raws, [raw_of(v, item) for item in v["inputs"] if item["expect"] == "accepted"])

    def test_order_free_vectors_survive_shuffles_and_repeats(self):
        for name, v in vectors():
            if not v["order_free"]:
                continue
            raws = [raw_of(v, item) for item in v["inputs"]]
            rng = random.Random(20261108)
            for round_ in range(20):
                stream = [r for r in raws for _ in range(rng.randint(1, 3))]
                rng.shuffle(stream)
                log = RefLog()
                results = [log.ingest(r) for r in stream]
                with self.subTest(vector=name, round=round_):
                    self.assertFalse([r for r in results if r.startswith("quarantined")])
                    self.assertEqual(ref_mastery(log.accepted), v["mastery"])

    def test_reference_catches_a_broken_rule(self):
        """对照实现自己也要能被测出错：把第 5 条规则去掉，attempt-inconsistent 就对不上。"""
        v = json.loads((KERNEL_VECTORS / "attempt-inconsistent.json").read_text(encoding="utf-8"))
        log = RefLog()
        for item in v["inputs"]:
            log.ingest(raw_of(v, item))
        global violated_rule
        original = violated_rule
        try:
            violated_rule = lambda evs: (None if original(evs) == 5 else original(evs))  # noqa: E731
            self.assertNotEqual(ref_mastery(log.accepted), v["mastery"])
        finally:
            violated_rule = original


class TestNumberVectors(unittest.TestCase):
    def test_format_and_reference(self):
        doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
        self.assertEqual(set(doc), {"about", "cases"})
        self.assertGreaterEqual(len(doc["cases"]), 20)
        for case in doc["cases"]:
            with self.subTest(json=case["json"]):
                self.assertEqual(set(case), {"json", "expect", "why"})
                value = json.loads(case["json"], parse_constant=_reject_constant)
                self.assertIsInstance(value, (int, float))
                self.assertEqual(_number_ok(value), case["expect"], case["why"])

    def test_vectors_catch_counting_raw_text_digits(self):
        """「按原始文字数小数位」是错误做法：0.000001 写成文字有 6 位，1e-6 写成文字没有小数点，两条期望相同才说明没用文字。"""
        cases = {c["json"]: c["expect"] for c in json.loads(NUMBERS.read_text(encoding="utf-8"))["cases"]}
        self.assertEqual(cases["0.000001"], cases["1e-6"])
        self.assertFalse(cases["1e-7"])


class TestVectorsCatchWrongAlgorithms(unittest.TestCase):
    """第 1 轮审阅第 6 条：新加的向量要能把常见的错误算法分辨出来。每个变体至少让一份向量对不上。"""

    def mismatches(self, **variant):
        saved = dict(VARIANT)
        VARIANT.update(variant)
        try:
            bad = []
            for name, v in vectors():
                log, _, checkpoints = run(v)
                if ref_mastery(log.accepted) != v["mastery"] or any(a != e for e, a in checkpoints):
                    bad.append(name)
            return bad
        finally:
            VARIANT.clear()
            VARIANT.update(saved)

    def test_spec_algorithm_matches_everything(self):
        self.assertEqual(self.mismatches(), [])

    def test_best_by_correct_count_is_caught(self):
        self.assertIn("mastery-best-ratio.json", self.mismatches(best="count"))

    def test_keeping_the_later_one_on_ties_is_caught(self):
        self.assertIn("mastery-best-tie-order.json", self.mismatches(best="tie-keep-last"))

    def test_zero_score_without_best_is_caught(self):
        self.assertEqual(self.mismatches(zero_best=False), ["mastery-zero-score.json"])

    def test_sorting_by_time_or_id_is_caught(self):
        for key in ("occurred_at", "event_id"):
            with self.subTest(key=key):
                self.assertIn("mastery-seq-order.json", self.mismatches(sort=key))

    def test_reporting_the_largest_rule_is_caught(self):
        self.assertIn("attempt-multi-rule.json", self.mismatches(pick="max"))


class TestGradingVectors(unittest.TestCase):
    def test_format_and_reference(self):
        doc = json.loads(GRADING.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(doc["cases"]), 40)
        used = set()
        for i, case in enumerate(doc["cases"]):
            with self.subTest(case=i, response=case["response"]):
                self.assertEqual(set(case), {"answer", "response", "expect", "why"})
                self.assertTrue(case["why"].strip())
                self.assertLessEqual(len(case["response"]), 32)
                answer = doc["answers"][case["answer"]]
                used.add(case["answer"])
                correct, misconception = ref_grade(answer, case["response"])
                self.assertEqual({"correct": correct, "misconception": misconception}, case["expect"], case["why"])
        self.assertEqual(used, set(doc["answers"]))


if __name__ == "__main__":
    unittest.main()
