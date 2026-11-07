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
        self.by_id, self.by_seq, self.accepted = {}, {}, []

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
        return "accepted"


# ---------------------------------------------------------------- 对照实现：掌握度
END = {"attempt.completed", "attempt.abandoned"}


def violated_rule(events):
    evs = sorted(events, key=lambda e: e["device_seq"])
    if len({e["device_id"] for e in evs}) > 1 or len({e["learner_id"] for e in evs}) > 1:
        return 1
    for e in evs:
        actor = e["actor"]
        if not (actor["type"] == "learner" and actor["id"] == e["learner_id"]):
            if not (e["verb"] == "attempt.abandoned" and actor["type"] == "system"):
                return 2
    if any(not same(e["content"], evs[0]["content"]) for e in evs):
        return 3
    starts = [i for i, e in enumerate(evs) if e["verb"] == "attempt.started"]
    ends = [i for i, e in enumerate(evs) if e["verb"] in END]
    if starts != [0] or len(ends) > 1 or (ends and ends[0] != len(evs) - 1):
        return 4
    tries = {}
    for e in evs:
        if e["verb"] == "item.answered":
            item = e["payload"]["item_id"]
            tries.setdefault(item, []).append(e["payload"]["try"])
    for seq in tries.values():
        if [float(t) for t in seq] != [float(i) for i in range(1, len(seq) + 1)]:
            return 5
    return None


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
        evs = sorted(evs, key=lambda e: e["device_seq"])
        if evs[-1]["verb"] != "attempt.completed":
            continue
        node = nodes[evs[0]["content"]["node_id"]]
        node["explored"] = True
        if evs[0]["content"]["activity_kind"] != "quiz":
            continue
        answered = {e["payload"]["item_id"] for e in evs if e["verb"] == "item.answered"}
        correct = {e["payload"]["item_id"] for e in evs
                   if e["verb"] == "item.answered" and float(e["payload"]["try"]) == 1 and e["payload"]["correct"] is True}
        if not answered:
            continue
        cand = (len(correct), len(answered))
        best = node["best"]
        if best is None or cand[0] * best[1] > best[0] * cand[1] or (cand[0] * best[1] == best[0] * cand[1] and cand[1] > best[1]):
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


def ref_grade(answer, response):
    r = response.strip().translate(FULLWIDTH)
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


def vectors():
    return [(p.name, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(KERNEL_VECTORS.glob("*.json"))]


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
                    self.assertTrue(set(item) <= {"event", "raw", "pad_to_bytes", "expect", "why"})
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
            log = RefLog()
            for item in v["inputs"]:
                log.ingest(raw_of(v, item))
            with self.subTest(vector=name):
                self.assertEqual(ref_mastery(log.accepted), v["mastery"])

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
