"""竖切片 6a：备份格式的 Python 参考实现自测，以及黄金向量和样例文件的生成和核对（docs/specs/backup.md）。

向量（app/vectors/backup-*.json）和样例文件（tests/fixtures/backup/）的期望值来自 tools/backup_ref.py 和手算，
不来自任何 JS 实现。重新生成：

    python tools/tests/test_backup_ref.py --write

已经存在的样例文件不会被覆盖（它们是永久的，规格 3.5）。CI 里的测试核对：磁盘上的向量就是参考实现现在算出的结果；
每条规则都有通过和不通过的样例；样例文件还能读。
"""
import base64
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import backup_ref as B  # noqa: E402

VEC = REPO / "app/vectors"
FIX = REPO / "tests/fixtures/backup"
KEY = "123456"
T0 = "2026-11-13T10:30:00.000Z"
ZERO16, ZERO7 = bytes(16), bytes(7)


# ================================================================ 测试数据
def u(tag):
    """合法的 ULID 主体：01JC4Y + 补零 + 标签（标签只用 Crockford 字符）。"""
    body = "01JC4Y" + tag.rjust(20, "0")
    assert re.fullmatch("[0-7][0-9A-HJKMNP-TV-Z]{25}", body), body
    return body


L, K, LR = "lrn_" + u("A"), "lrn_" + u("K"), "lrn_" + u("R1")      # 备份的孩子、另一个孩子、干净设备自己建的身份
DB, DE, DR = "dev_" + u("B"), "dev_" + u("E"), "dev_" + u("R")      # 做备份的设备、以前导入过的设备、恢复到的设备
IMP_A, IMP_P, IMP_2, IMP_M = "imp_" + u("A1"), "imp_" + u("P1"), "imp_" + u("P2"), "imp_" + u("M1")
SYN = "syn_" + u("S1")


def rel(name, extra):
    """一个 release/1 清单的原文（缩进写法，结尾带换行，像网站上的 release.json）。content_hash 照规范 JSON 算。"""
    body = {"engine_min": 1, "contracts": ["activity/1.0"], "nodes": [], "activities": [], "assets": [], **extra}
    h = hashlib.sha256(B.canonical(body).encode("utf-8")).hexdigest()
    doc = {"schema": "release/1", "release_id": "rel_" + h, "content_hash": h, "source_commit": name * 40, **body}
    return {"release_id": "rel_" + h, "raw": json.dumps(doc, ensure_ascii=False, indent=2) + "\n"}


REL1 = rel("a", {"assets": [{"path": "assets/a.svg", "bytes": 10, "sha256": "1" * 64}]})
REL0 = rel("b", {})
CONTENT = {"node_id": "math.number.fraction-intro", "activity_id": "act.quiz.fraction-intro-01", "activity_kind": "quiz",
           "activity_version": 1, "content_release": REL1["release_id"]}


def ev(tag, dev, seq, occ, verb, att, payload, learner=L, **extra):
    e = {"schema": "event/2", "event_id": "evt_" + u(tag), "learner_id": learner, "device_id": dev, "device_seq": seq,
         "occurred_at": occ, "actor": {"type": "learner", "id": learner}, "verb": verb}
    if att:
        e["attempt_id"] = "att_" + u(att)
        e["content"] = CONTENT
    e["payload"] = payload
    e.update(extra)
    return e


def js(e):
    """JSON.stringify 的写法（外壳存的原文就是这样）。"""
    return json.dumps(e, ensure_ascii=False, separators=(",", ":"))


def eid(raw):
    return json.loads(raw)["event_id"]


EV = {
    "B1": ev("B01", DB, 1, "2026-11-12T01:00:00.000Z", "attempt.started", "T1", {"mode": "first", "grader": "grade/1"}),
    "B2": ev("B02", DB, 2, "2026-11-12T01:00:10.000Z", "item.answered", "T1", {"item_id": "q1", "response": "b", "correct": True, "try": 1, "hints_used": 0}),
    "B3": ev("B03", DB, 3, "2026-11-12T01:00:20.000Z", "item.answered", "T1", {"item_id": "q2", "response": "a", "correct": False, "try": 1, "hints_used": 0, "misconception": "part-vs-rest"}),
    "B4": ev("B04", DB, 4, "2026-11-12T01:00:30.000Z", "answer.revealed", "T1", {"item_id": "q2"}),
    "B5": ev("B05", DB, 5, "2026-11-12T01:01:05.000Z", "attempt.completed", "T1", {"duration_ms": 65000}),
    "E1": ev("E01", DE, 1, "2026-11-10T08:00:00.000Z", "attempt.started", "T2", {"mode": "first"}),
    "E2": ev("E02", DE, 2, "2026-11-10T08:00:30.000Z", "attempt.completed", "T2", {"duration_ms": 30000}),
    "B6": ev("B06", DB, 6, "2026-11-13T02:00:00.000Z", "attempt.started", "T3", {"mode": "retry"}),
    "B7": ev("B07", DB, 7, "2026-11-13T02:00:09.000Z", "item.answered", "T3", {"item_id": "q1", "response": "二分之一", "correct": False, "try": 1, "hints_used": 1}),
}
RAW = {k: js(v) for k, v in EV.items()}
RAW["E1"] = json.dumps(EV["E1"], ensure_ascii=False, indent=2)          # 别的程序写的原文：记号之间有换行和空格
RAW["X'"] = js(dict(EV["B2"], payload=dict(EV["B2"]["payload"], response="c")))  # 和 B2 同 event_id、内容不同：冲突
FIX_ORDER = ["B1", "B2", "B3", "B4", "B5", "E1", "E2", "X'", "B6", "B7"]


def rc_local(k, at):
    return {"event_id": eid(RAW[k]), "recorded_at": at, "source": "local"}


def rc_import(k, at, batch):
    return {"event_id": eid(RAW[k]), "recorded_at": at, "source": "import", "batch_id": batch}


def b64(b):
    return base64.b64encode(bytes(b)).decode("ascii")


SALT_E = b64(range(0x11, 0x21))
IMPORT_A = {"schema": "import-record/1", "batch_id": IMP_A, "imported_at": "2026-11-11T09:00:00.000Z", "source": "backup",
            "partial": False, "file_created_at": "2026-11-10T09:00:00.000Z", "file_device_id": DE, "file_salt": SALT_E,
            "accepted": 2, "duplicate": 0, "not_yet_known": 0, "quarantined_new": 0, "quarantined_skipped": 0, "archived": 1, "releases": 0}


def fixture_snapshot():
    """做备份的设备 B 的存储（样例文件的内容）。收据、导入记录、发布包故意不按顺序，键的顺序也打乱，写的时候要排好。"""
    at = lambda m: f"2026-11-12T01:{m:02d}:00.500Z"  # noqa: E731
    receipts = [rc_local(k, at(i)) for i, k in enumerate(["B1", "B2", "B3", "B4", "B5"])]
    receipts += [rc_import(k, "2026-11-11T09:00:00.000Z", IMP_A) for k in ["E1", "E2"]]
    receipts += [rc_local("B6", "2026-11-13T02:00:00.100Z"), rc_local("B7", "2026-11-13T02:00:09.100Z")]
    receipts = [dict(reversed(list(r.items()))) for r in reversed(receipts)]
    return {
        "identity": {"learner_id": L, "device_id": DB},
        "nextSeq": 8,
        "inbox": [RAW[k] for k in FIX_ORDER],
        "receipts": receipts,
        "imports": [dict(reversed(list(IMPORT_A.items())))],
        "archive": [{"kind": "receipt", "v": {"source": "local", "recorded_at": "2026-11-10T08:00:00.200Z", "event_id": eid(RAW["E1"])}}],
        "releases": [REL1],
        "recoveryKey": {"digits": KEY, "confirmed_at": "2026-11-13T10:00:00.000Z"},
        "restoring": None,
    }


def empty_snapshot(learner="lrn_01JC4Y0000000000000000000A", device="dev_01JC4Y0000000000000000000B"):
    return {"identity": {"learner_id": learner, "device_id": device}, "nextSeq": 1, "inbox": [], "receipts": [], "imports": [],
            "archive": [], "releases": [], "recoveryKey": None, "restoring": None}


FIX_CREATED = T0
FIX_COMMIT = "d08341b"
FIX_NONE = {"salt": bytes(range(16)), "nonce_prefix": bytes(range(0xA0, 0xA7))}
FIX_GZIP = {"salt": bytes(range(0x10, 0x20)), "nonce_prefix": bytes(range(0xB0, 0xB7))}


def fixture_doc():
    return B.write_manifest_doc(fixture_snapshot(), created_at=FIX_CREATED, app_commit=FIX_COMMIT)


def fixture_file(kind):
    p = FIX_NONE if kind == "none" else FIX_GZIP
    return B.encode_backup(fixture_doc(), digits=KEY, created_at=FIX_CREATED, iterations=600000, chunk_size=64, compression=kind, **p)


# ================================================================ 向量生成用的小工具
def hx(b):
    return bytes(b).hex()


def stored_gzip(data, mtime=0):
    """手拼的 gzip 成员：deflate 只用「不压缩」块（BTYPE=00），和 zlib 的版本无关，字节可以手算。"""
    out = b"\x1f\x8b\x08\x00" + mtime.to_bytes(4, "little") + b"\x00\xff"
    blocks = [data[i:i + 65535] for i in range(0, len(data), 65535)] or [b""]
    for i, blk in enumerate(blocks):
        n = len(blk)
        out += bytes([1 if i == len(blocks) - 1 else 0]) + n.to_bytes(2, "little") + (n ^ 0xFFFF).to_bytes(2, "little") + blk
    return out + zlib.crc32(data).to_bytes(4, "little") + (len(data) & 0xFFFFFFFF).to_bytes(4, "little")


def enc(stream, *, compression, salt=ZERO16, prefix=ZERO7, iterations=600000, chunk=64, created=T0, digits=KEY):
    return B.encrypt_stream(stream, digits=digits, created_at=created, salt=salt, nonce_prefix=prefix, iterations=iterations,
                            chunk_size=chunk, compression=compression)


def header_bounds(file):
    s = file.index(b"\n") + 1
    return s, file.index(b"\n", s)


def apply_ops(file, ops):
    """向量里的变换，测试里照做：truncate、xor、append、swap、replace。"""
    f = bytearray(file)
    for op in ops:
        k = op["op"]
        if k == "truncate":
            del f[op["len"]:]
        elif k == "xor":
            f[op["at"]] ^= op["mask"]
        elif k == "append":
            f += bytes.fromhex(op["hex"])
        elif k == "swap":
            a, b, n = op["a"], op["b"], op["len"]
            x, y = bytes(f[a:a + n]), bytes(f[b:b + n])
            f[a:a + n], f[b:b + n] = y, x
        elif k == "replace":
            f[op["start"]:op["end"]] = bytes.fromhex(op["hex"])
        else:
            raise ValueError(k)
    return bytes(f)


def norm(v):
    """向量里存的 JSON：整数值的小数写成整数（JS 读出来就是这样）。"""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return [norm(x) for x in v]
    return v


def dump_store(s):
    """比较用的存储形状：收据按 event_id、导入记录按 batch_id、发布包按 release_id 排序；收件表、archive 保持顺序。"""
    return norm({"identity": s["identity"], "nextSeq": s["nextSeq"], "inbox": list(s["inbox"]),
                 "receipts": sorted(s["receipts"], key=lambda r: r["event_id"]),
                 "imports": sorted(s["imports"], key=lambda r: r["batch_id"]), "archive": list(s["archive"]),
                 "releases": sorted(s["releases"], key=lambda r: r["release_id"]),
                 "recoveryKey": s.get("recoveryKey"), "restoring": s.get("restoring")})


# ================================================================ backup-key.json
def key_vectors():
    gen = [
        {"u32": [4294000000, 4294967295, 7], "expect": "000007",
         "why": "2.1：4294000000、4294967295 都 ≥ 4294000000，丢掉重取；7 mod 10^6 = 7，左边补零到 6 位（规格测试表第 1 行）"},
        {"u32": [123456789], "expect": "456789", "why": "2.1：123456789 mod 1000000 = 456789"},
        {"u32": [4293999999], "expect": "999999", "why": "2.1：4293999999 < 4294000000，不丢；mod 10^6 = 999999（丢弃线的边界，差一就丢）"},
        {"u32": [0], "expect": "000000", "why": "2.1：0 mod 10^6 = 0，补零成 000000"},
        {"u32": [4294000000, 1000000], "expect": "000000", "why": "2.1：第一个正好等于丢弃线，丢掉；1000000 mod 10^6 = 0"},
        {"u32": [482105], "expect": "482105", "why": "2.1：小于 10^6 的数原样，正好 6 位"},
    ]
    for g in gen:
        it = iter(g["u32"])
        assert B.generate_key(lambda: next(it)) == g["expect"], g
    fmt = [{"digits": "482105", "expect": "482 105", "why": "2.1：显示成两组，中间一个空格"},
           {"digits": "000007", "expect": "000 007", "why": "2.1：补的零也照样分组"}]
    P = []

    def p(inp, expect, why):
        r = B.parse_key(inp)
        exp = {"ok": True, "digits": expect} if re.fullmatch("[0-9]{6}", expect) else {"ok": False, "error": expect}
        assert r == exp, (inp, r, exp)
        P.append({"input": inp, "expect": exp, "why": why})

    p("482105", "482105", "2.2：本来就是 6 个 ASCII 数字")
    p("482 105", "482105", "2.2 第 2 步：去掉 U+0020（显示的写法能原样输回来）")
    p("482-105", "482105", "2.2 第 2 步：去掉 -（U+002D）")
    p("４８２１０５", "482105", "2.2 第 1 步：NFKC 把全角数字 U+FF14… 变成半角")
    p("４８２　１０５", "482105", "2.2：全角数字 + 全角空格 U+3000（NFKC 变 U+0020，再被去掉）")
    p("482－105", "482105", "2.2：全角横线 U+FF0D 经 NFKC 变成 -，再被去掉")
    p("482\u2212105", "482105", "2.2 第 2 步：U+2212（减号）NFKC 不变，在封闭表里，去掉")
    p("482\u30fc105", "482105", "2.2 第 2 步：U+30FC（长音符，中文输入法常打出来）在封闭表里，去掉")
    p("48\u20102\u2011\u2012\u2013\u2014\u2015105", "482105", "2.2 第 2 步：U+2010～U+2015 都在封闭表里")
    p("\t482\u00a0105\r\n\x0b\x0c", "482105", "2.2 第 2 步：U+0009～U+000D、U+00A0 都在封闭表里")
    p("482\u2003105", "482105", "2.2 第 1 步：U+2003（全身空格）NFKC 变成 U+0020，第 2 步去掉")
    p("①②③④⑤⑥", "123456", "2.2 第 1 步：NFKC 把带圈数字变成 ASCII 数字，之后照常")
    p("48210O", "key_not_digits", "2.2 第 3 步：字母 O 不是 0～9（规格测试表）")
    p("4821O", "key_not_digits", "2.2：既有字母又少一位，第 3 步在第 4 步之前，报「只有数字」（规格测试表）")
    p("48210", "key_length", "2.2 第 4 步：五位")
    p("4821050", "key_length", "2.2 第 4 步：七位")
    p("", "key_length", "2.2 第 4 步：空的，0 个数字")
    p("   ", "key_length", "2.2：只有空格，去掉以后 0 个数字")
    p("482\ufeff105", "key_not_digits", "2.2：U+FEFF 不在封闭表里（JS 的 \\s 包括它，不能用 \\s）")
    p("482\u2028105", "key_not_digits", "2.2：U+2028 不在封闭表里，NFKC 也不变它（JS 的 \\s 包括它）")
    p("482\u0085105", "key_not_digits", "2.2：U+0085 不在封闭表里（Python 的 isspace 认它是空白，不能用）")
    p("482\u200b105", "key_not_digits", "2.2：U+200B（零宽空格）不在封闭表里")
    p("482_105", "key_not_digits", "2.2：下划线不在封闭表里")
    p("٤٨٢١٠٥", "key_not_digits", "2.2 第 3 步：阿拉伯-印度数字 NFKC 不变，不是 0～9（不能用「是不是数字」的通用判断）")
    p("４８２１０", "key_length", "2.2：全角五位，规整后 5 个数字")
    return {"about": "恢复密钥：生成（2.1）、显示、输入规整（2.2）。backup.js 的 generateKey、formatKey、parseKey。",
            "generate": gen, "format": fmt, "parse": P}


# ================================================================ backup-file.json
def min_doc(commit="275c460"):
    return B.write_manifest_doc(empty_snapshot(), created_at=T0, app_commit=commit)


def manifest_doc_with(first_line_obj, rest=b""):
    return B.line(first_line_obj) + rest


def file_vectors():
    out = {"about": "备份文件的读写（3.1～3.3、3.8 第 1～9 步）。字节都是小写十六进制。test 里照 ops 从 from 指的文件变换出坏文件。",
           "key": KEY, "files": {}, "encode": [], "decode": [], "read": [], "build": []}
    files = out["files"]

    def add(name, file, why, **meta):
        files[name] = {"hex": hx(file), "sha256": hashlib.sha256(file).hexdigest(), "bytes": len(file), "why": why, **meta}
        return file

    md = min_doc()
    assert len(md) == 351 and hashlib.sha256(md).hexdigest() == "8b2a6fb0b02c950562a03ce1e04fdd384c37bdd8bd262e74d96ed7d6d1f58c70"
    fmin = B.encode_backup(md, digits=KEY, created_at=T0, salt=ZERO16, nonce_prefix=ZERO7, iterations=600000, chunk_size=64)
    add("min", fmin, "规格测试表第 3 行：密钥 123456、iterations 600000、salt 和 nonce_prefix 全零、none、chunk_size 64，"
        "明文只有清单和 end 两行（351 字节，SHA-256 8b2a6fb0…，和 pr-129 第 2、3 轮的明文相同）。6 块：5 个满块 + 末块 31 字节。"
        "Python 和 Node 22 Web Crypto 各算一遍，逐字节相同（747 字节，SHA-256 80916e42…）。iterations 换成 1000 时得到 pr-129 第 3 轮的 745 字节 77d96f1f…",
        doc_hex=hx(md))
    mdf = min_doc("a1ddb1e873b65ecabf6154c9a423b0b713fa1672")
    assert len(mdf) == 384
    ffull = B.encode_backup(mdf, digits=KEY, created_at=T0, salt=ZERO16, nonce_prefix=ZERO7, iterations=600000, chunk_size=64)
    add("min_full", ffull, "同 min，但 app_commit 是 40 位，明文 351 − 7 + 40 = 384 = 6 × 64 字节，末块是满块（3.2：最后一块不短也要用 0x01）。"
        "Node 22 Web Crypto 独立算出 780 字节、SHA-256 2411d3dd…，和这里相同", doc_hex=hx(mdf))
    two = (b"0123456789abcdef" * 8)
    ftwo = B.encode_backup(two, digits=KEY, created_at=T0, salt=ZERO16, nonce_prefix=ZERO7, iterations=600000, chunk_size=64)
    add("two_chunks", ftwo, "规格测试表第 4 行：明文正好 2 个整块（128 字节 ASCII，不是清单；decodeBackup 不查清单）。第 0 块随机数末字节 0x00、第 1 块 0x01",
        doc_hex=hx(two))
    fixn = fixture_file("none")
    add("fixture_none", fixn, "tests/fixtures/backup/v1-none.curio 的全部字节（none 模式逐字节确定）", doc_hex=hx(fixture_doc()))
    f128 = B.encode_backup(md, digits=KEY, created_at=T0, salt=ZERO16, nonce_prefix=ZERO7, iterations=600000, chunk_size=128)
    add("chunk128", f128, "3.1：读的程序接受 64～16777216 之间的 2 的幂，128 可以；3 块（128、128、95）", doc_hex=hx(md))
    f100k = B.encode_backup(md, digits=KEY, created_at=T0, salt=ZERO16, nonce_prefix=ZERO7, iterations=100000, chunk_size=64)
    add("iter100000", f100k, "3.1：读的程序接受 100000（下限，含）", doc_hex=hx(md))
    gz = stored_gzip(md)
    fgz = enc(gz, compression="gzip")
    add("gzip_min", fgz, "3.3：明文是一个 gzip 成员（FLG=0、MTIME=0，deflate 用不压缩的块，手拼，字节和 zlib 版本无关）", doc_hex=hx(md), stream_hex=hx(gz))
    gz2 = stored_gzip(md[:100]) + stored_gzip(md[100:])
    add("gzip_two", enc(gz2, compression="gzip"), "3.3 读：两个首尾相接的成员，解出来是两段拼起来（规格测试表「gzip 两个成员」）", doc_hex=hx(md))
    add("gzip_zeros", enc(gz + b"\x00\x00\x00\x00", compression="gzip"), "3.3：最后一个成员后面补了 4 个零字节 → 3.8 第 7 步")
    add("gzip_garbage", enc(gz + b"abc", compression="gzip"), "3.3：成员后面跟着不是 1F 8B 开头的字节 → 3.8 第 7 步")
    add("gzip_magic_only", enc(gz + b"\x1f\x8b", compression="gzip"), "3.3：成员后面只有 1F 8B 两个字节，第二个成员不完整 → 3.8 第 7 步")
    bad_crc = bytearray(gz)
    bad_crc[-8] ^= 1
    add("gzip_bad_crc", enc(bytes(bad_crc), compression="gzip"), "3.3：CRC32 不对 → 3.8 第 7 步")
    bad_isize = bytearray(gz)
    bad_isize[-4] ^= 1
    add("gzip_bad_isize", enc(bytes(bad_isize), compression="gzip"), "3.3：ISIZE 不对 → 3.8 第 7 步")
    add("gzip_truncated", enc(gz[:-4], compression="gzip"), "3.3：成员少了结尾的 ISIZE → 3.8 第 7 步")
    add("gzip_not_gzip", enc(md, compression="gzip"), "文件头说 gzip，明文却没压缩（不是 1F 8B 开头）→ 3.8 第 7 步")
    add("none_bom", enc(b"\xef\xbb\xbf" + md, compression="none"), "第 4 节：明文以 BOM 开头 → 3.8 第 9 步「坏了」")
    bad8 = md.replace(b"275c460", b"275c\xff60")
    add("none_bad_utf8", enc(bad8, compression="none"), "第 4 节：明文里有 0xFF（不是合法 UTF-8）→ 3.8 第 9 步")
    sur = md.replace(b'"275c460"', b'"275\xed\xa0\x800"')
    add("none_surrogate_utf8", enc(sur, compression="none"), "第 4 节：明文里有 ED A0 80（UTF-8 编出来的代理项，严格解码不认）→ 3.8 第 9 步")
    m9 = manifest_doc_with({"schema": "backup-manifest/9", "created_at": T0, "anything": "以后的格式"}, b"\x00\x01 not json\n")
    fm9 = add("manifest9", enc(m9, compression="none"), "清单 backup-manifest/9，后面的行是以后的格式（这一版读不懂也不该去读）→ 3.8 第 10 步", doc_hex=hx(m9))
    m9g = enc(stored_gzip(m9), compression="gzip")
    add("manifest9_gzip", m9g, "同 manifest9，gzip 模式", doc_hex=hx(m9))
    fbadcounts = enc(md.replace(b'"inbox":0', b'"inbox":1'), compression="none")
    add("doc_bad_counts", fbadcounts, "能解开，但清单的 counts.inbox 是 1 而没有收件行（end 的 lines 也对不上）→ 3.8 第 11 步")

    # ---- encode（逐字节）
    for name, doc, kw in [("min", md, {}), ("min_full", mdf, {}), ("two_chunks", two, {}), ("chunk128", md, {"chunkSize": 128}),
                          ("iter100000", md, {"iterations": 100000})]:
        out["encode"].append({"file": name, "doc_hex": hx(doc), "params": {"digits": KEY, "createdAt": T0, "salt_hex": hx(ZERO16),
                              "noncePrefix_hex": hx(ZERO7), "iterations": kw.get("iterations", 600000), "chunkSize": kw.get("chunkSize", 64),
                              "compression": "none"}, "why": files[name]["why"]})
    out["encode"].append({"file": "fixture_none", "doc_hex": hx(fixture_doc()), "params": {"digits": KEY, "createdAt": FIX_CREATED,
                          "salt_hex": hx(FIX_NONE["salt"]), "noncePrefix_hex": hx(FIX_NONE["nonce_prefix"]), "iterations": 600000,
                          "chunkSize": 64, "compression": "none"}, "why": "样例文件 v1-none.curio：salt 00..0f、nonce_prefix a0..a6"})

    # ---- decode
    hs, he = header_bounds(fmin)
    body = he + 1
    hl = fmin[hs:he]
    hobj = json.loads(hl)
    D = out["decode"]

    def dec(name, src, ops, expect, why, digits=KEY, max_plain=None):
        f = apply_ops(bytes.fromhex(files[src]["hex"]) if src else b"", ops)
        r = B.decode_backup(f, digits, B.DEFAULT_MAX_PLAIN if max_plain is None else max_plain)
        if expect == "ok":
            assert r["ok"], (name, r)
            exp = {"ok": True, "doc_hex": hx(r["doc"]), "header": r["header"], "headerLine_hex": hx(r["headerLine"])}
        else:
            assert r == {"ok": False, "error": expect}, (name, r, expect)
            exp = {"ok": False, "error": expect}
        case = {"name": name, "from": src, "ops": ops, "digits": digits, "expect": exp, "why": why}
        if max_plain is not None:
            case["maxPlain"] = max_plain
        D.append(case)

    def rep_header(text):
        return [{"op": "replace", "start": hs, "end": he, "hex": text.encode("utf-8").hex()}]

    def hdr(**ch):
        h = dict(hobj, **ch)
        return B.json.dumps(h, ensure_ascii=False, separators=(",", ":"))

    for name in ["min", "min_full", "two_chunks", "fixture_none", "chunk128", "iter100000", "gzip_min", "gzip_two"]:
        dec(f"ok_{name}", name, [], "ok", "好文件能解开：" + files[name]["why"])
    dec("ok_max_plain_equal", "min", [], "ok", "3.3：大小上限是「超过」才停；明文正好 351 字节、上限 351 可以", max_plain=351)
    dec("too_big_none", "min", [], "too_big", "3.8 第 8 步：明文 351 字节超过上限 350", max_plain=350)
    dec("too_big_gzip", "gzip_min", [], "too_big", "3.8 第 8 步：解压后 351 字节超过上限 350（按解压后的大小算）", max_plain=350)
    dec("incomplete_before_too_big", "gzip_zeros", [], "incomplete", "3.8：第 7 步（gzip 坏了）在第 8 步（太大）之前", max_plain=10)
    # 第 2、3 步
    dec("not_curio_empty", None, [], "not_curio", "3.8 第 2 步：空文件（不到 15 字节）")
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452") + bytes(64)
    dec("not_curio_png", None, [{"op": "append", "hex": png.hex()}], "not_curio", "3.8 第 2 步：改了名字的图片（PNG 的开头），前 13 字节不是 CURIO-BACKUP/（规格第 12 节演练第 5 步）")
    dec("not_curio_14_bytes", "min", [{"op": "truncate", "len": 14}], "not_curio", "3.8 第 2 步：只有 CURIO-BACKUP/1，14 字节，不到 15 字节")
    dec("not_curio_lowercase", "min", [{"op": "xor", "at": 0, "mask": 0x20}], "not_curio", "3.1：第一行必须正好是大写的 CURIO-BACKUP/（改第一行一个字节，见歧义 5）")
    dec("not_curio_leading_zero", "min", [{"op": "replace", "start": 13, "end": 14, "hex": b"01".hex()}], "not_curio", "3.1：数字不能带前导零（CURIO-BACKUP/01）")
    dec("not_curio_zero", "min", [{"op": "replace", "start": 13, "end": 14, "hex": b"0".hex()}], "not_curio", "3.1：数字必须是正整数（CURIO-BACKUP/0）")
    dec("not_curio_no_number", "min", [{"op": "replace", "start": 13, "end": 14, "hex": b"".hex()}], "not_curio", "3.1：CURIO-BACKUP/ 后面直接是 \\n，没有数字")
    dec("not_curio_crlf", "min", [{"op": "replace", "start": 14, "end": 15, "hex": b"\r\n".hex()}], "not_curio", "3.1：数字后面必须紧跟 \\n，\\r\\n 不行")
    dec("not_curio_no_newline", None, [{"op": "append", "hex": b"CURIO-BACKUP/2".hex()}], "not_curio", "3.1：15 字节以内没有 \\n（CURIO-BACKUP/2 后面什么都没有）")
    dec("update_v2", "min", [{"op": "replace", "start": 13, "end": 14, "hex": b"2".hex()}], "update", "3.8 第 3 步：第一行 /2 →「请先更新」（规格测试表）")
    dec("update_v10", "min", [{"op": "replace", "start": 13, "end": 14, "hex": b"10".hex()}], "update", "3.8 第 3 步：/10 不是 1（按数字串比，不是只看第一位）")
    dec("update_huge", "min", [{"op": "replace", "start": 13, "end": 14, "hex": b"99999999999999999999".hex()}], "update", "3.8 第 3 步：很长的数也只是「不是 1」，按字符串比较，不转成数")
    dec("update_before_header", "min", [{"op": "replace", "start": 13, "end": he, "hex": b"2\nnot a header".hex()}], "update", "3.8：第 3 步在第 4 步之前，/2 后面是什么都不看")
    # 第 4 步
    dec("corrupt_line1_only", "min", [{"op": "truncate", "len": 15}], "corrupt", "3.8 第 4 步：只有第一行，没有文件头的 \\n")
    dec("corrupt_header_no_newline", "min", [{"op": "truncate", "len": he}], "corrupt", "3.8 第 4 步：文件头后面没有 \\n（文件在文件头里断了）")
    dec("corrupt_header_brace", "min", [{"op": "xor", "at": hs, "mask": ord("{") ^ ord("[")}], "corrupt", "3.8 第 4 步：改文件头一个字节，{ 变 [，不是 JSON 对象（规格测试表「改文件头一个字节」）")
    i = fmin.index(b"curio-backup/1", hs)
    dec("corrupt_header_format_byte", "min", [{"op": "xor", "at": i, "mask": 1}], "corrupt", "3.8 第 4 步：改文件头 format 里的一个字节，值不对")
    i = fmin.index(b"10:30:00", hs)
    dec("incomplete_header_created_at", "min", [{"op": "xor", "at": i + 4, "mask": ord("3") ^ ord("1")}], "incomplete",
        "改文件头 created_at 的一位（10:30 → 10:31）：文件头仍然合格，key_check 也对（密钥不依赖 created_at），但 AAD 变了，所有块都解不开 → 3.8 第 6 步。见歧义 5：规格测试表把「改文件头一个字节」写成「坏了」，按 3.8 的顺序这一种是第 6 步")
    dup = hl.decode().replace('{"format":"curio-backup/1",', '{"format":"curio-backup/1","format":"curio-backup/1",')
    dec("corrupt_header_dup_key", "min", rep_header(dup), "corrupt", "3.1 写法对：重复的键，重写后少了一个键，和原来不同")
    dec("corrupt_header_space", "min", rep_header(hl.decode().replace('"kdf":', '"kdf": ')), "corrupt", "3.1 写法对：多了一个空格")
    dec("corrupt_header_trailing_space", "min", rep_header(hl.decode() + " "), "corrupt", "3.1 写法对：行尾多一个空格（JSON 解析得出来，重写不同）")
    dec("corrupt_header_cr", "min", rep_header(hl.decode() + "\r"), "corrupt", "3.1 写法对：行尾带 \\r")
    dec("corrupt_header_escape", "min", rep_header(hl.decode().replace('"cipher"', '"\\u0063ipher"')), "corrupt", "3.1 写法对：别的转义写法（\\u0063）")
    dec("corrupt_header_order", "min", rep_header(hl.decode().replace('"kdf":"pbkdf2-sha256+hkdf-sha256","iterations":600000,', '"iterations":600000,"kdf":"pbkdf2-sha256+hkdf-sha256",')), "corrupt", "3.1：字段顺序不对，重写后不同")
    dec("corrupt_header_b64_noncanon", "min", rep_header(hdr(salt="AAAAAAAAAAAAAAAAAAAAAB==")), "corrupt", "3.1：不规范的 Base64（最后一个字符的低位不是 0，解码后再编码成 …AA==，不同）")
    dec("corrupt_header_b64_nopad", "min", rep_header(hdr(salt="AAAAAAAAAAAAAAAAAAAAAA")), "corrupt", "3.1：Base64 没有 = 补位")
    dec("corrupt_header_b64_urlsafe", "min", rep_header(hdr(salt="-_AAAAAAAAAAAAAAAAAAAA==")), "corrupt", "3.1：不是标准 Base64（URL 安全字母表）")
    dec("corrupt_header_salt15", "min", rep_header(hdr(salt=b64(bytes(15)))), "corrupt", "3.1：salt 解码后 15 字节（规格测试表）")
    dec("corrupt_header_key_check17", "min", rep_header(hdr(key_check=b64(bytes(17)))), "corrupt", "3.1：key_check 解码后 17 字节")
    dec("corrupt_header_nonce8", "min", rep_header(hdr(nonce_prefix=b64(bytes(8)))), "corrupt", "3.1：nonce_prefix 解码后 8 字节")
    dec("corrupt_header_iter99999", "min", rep_header(hdr(iterations=99999)), "corrupt", "3.1：iterations 99999 低于下限 100000（规格测试表）")
    dec("corrupt_header_iter_fraction", "min", rep_header(hl.decode().replace('"iterations":600000', '"iterations":600000.5')), "corrupt", "3.1：iterations 不是整数 600000.5（规格测试表）")
    dec("corrupt_header_iter_dot0", "min", rep_header(hl.decode().replace('"iterations":600000', '"iterations":600000.0')), "corrupt", "3.1：600000.0 在 Python 里不是 int、在 JS 里重写成 600000 和原文不同；两边都是第 4 步")
    dec("corrupt_header_iter_string", "min", rep_header(hdr(iterations="600000")), "corrupt", "3.1：iterations 是字符串")
    dec("corrupt_header_iter_too_many", "min", rep_header(hdr(iterations=10000001)), "corrupt", "3.1：iterations 超过上限 10000000")
    dec("corrupt_header_key_id", "min", rep_header(hdr(key_id="839ead5e")), "corrupt", "3.1：多一个字段 key_id（第 2 稿的旧字段，规格测试表）")
    dec("corrupt_header_missing_field", "min", rep_header(B.json.dumps({k: v for k, v in hobj.items() if k != "compression"}, separators=(",", ":"))), "corrupt", "3.1：少一个字段 compression")
    dec("corrupt_header_format2", "min", rep_header(hdr(format="curio-backup/2")), "corrupt", "3.1：第一行 /1 而 format 是 curio-backup/2 →「坏了」（规格测试表）")
    dec("corrupt_header_kdf", "min", rep_header(hdr(kdf="hkdf-sha256")), "corrupt", "3.1：kdf 不是固定值（第 2 稿的旧值）")
    dec("corrupt_header_cipher", "min", rep_header(hdr(cipher="aes-128-gcm")), "corrupt", "3.1：cipher 不是固定值")
    dec("corrupt_header_created_at", "min", rep_header(hdr(created_at="2026-11-13T10:30:00Z")), "corrupt", "3.1：created_at 不是事件规格第 1 节的格式（没有毫秒）")
    dec("corrupt_header_chunk100", "min", rep_header(hdr(chunk_size=100)), "corrupt", "3.1：chunk_size 100 不是 2 的幂（规格测试表）")
    dec("corrupt_header_chunk32", "min", rep_header(hdr(chunk_size=32)), "corrupt", "3.1：chunk_size 32 低于 64")
    dec("corrupt_header_chunk_big", "min", rep_header(hdr(chunk_size=33554432)), "corrupt", "3.1：chunk_size 2^25 超过 16777216")
    dec("corrupt_header_compression", "min", rep_header(hdr(compression="zstd")), "corrupt", "3.1：compression 只能是 gzip 或 none")
    long_hdr = hl.decode()[:-1] + " " * 4100 + "}"
    dec("corrupt_header_too_long", "min", rep_header(long_hdr), "corrupt", "3.1：文件头超过 4096 字节（规格测试表）")
    dec("corrupt_header_4097_no_newline", "min", [{"op": "truncate", "len": hs}, {"op": "append", "hex": (b"x" * 5000).hex()}], "corrupt", "3.1：第二行读到第 4097 个字节还没有 \\n")
    dec("corrupt_header_not_utf8", "min", [{"op": "xor", "at": i, "mask": 0x80}], "corrupt", "3.8 第 4 步：文件头里有不是 UTF-8 的字节")
    dec("corrupt_before_wrong_key", "min", rep_header(hl.decode().replace('"kdf":', '"kdf": ')), "corrupt",
        "3.8：文件头写法不对，而且密钥也不对 →「坏了」，第 4 步在第 5 步之前（规格测试表）", digits="654321")
    # 第 5 步
    dec("wrong_key", "min", [], "wrong_key", "3.8 第 5 步：差一个数的密钥 123457，key_check 不同（规格第 12 节演练第 5 步）", digits="123457")
    dec("wrong_key_000000", "min", [], "wrong_key", "3.8 第 5 步：000000", digits="000000")
    dec("wrong_key_before_bad_body", "min", [{"op": "xor", "at": body + 90, "mask": 1}], "wrong_key", "3.8：错的密钥，而且密文也坏了 →「密钥不对」，第 5 步在第 6 步之前（规格测试表）", digits="123457")
    dec("wrong_key_before_empty_body", "min", [{"op": "truncate", "len": body}], "wrong_key", "3.8：错的密钥、密文是空的 → 第 5 步先停", digits="123457")
    # 第 6 步（min：明文 351 = 5×64 + 31；密文块 5×80 + 47）
    dec("incomplete_empty_body", "min", [{"op": "truncate", "len": body}], "incomplete", "3.2：文件头后面 0 字节 → 3.8 第 6 步")
    dec("incomplete_block_boundary", "min", [{"op": "truncate", "len": body + 5 * 80}], "incomplete", "3.2：截断在块边界，第 4 块（下标）被当成末块用 0x01 去解，失败（规格测试表）")
    dec("incomplete_drop_last_byte", "min", [{"op": "truncate", "len": len(fmin) - 1}], "incomplete", "3.2：删掉最后一个字节，末块的认证标签不对（规格测试表）")
    dec("incomplete_last_16", "min", [{"op": "truncate", "len": body + 5 * 80 + 16}], "incomplete", "3.2：末块只剩 16 字节，不足 17（规格测试表）")
    dec("incomplete_last_17", "min", [{"op": "truncate", "len": body + 5 * 80 + 17}], "incomplete", "3.2：末块 17 字节，长度够，但认证失败")
    dec("incomplete_extra_block", "min", [{"op": "append", "hex": fmin[body:body + 80].hex()}], "incomplete", "3.2：尾部多出整整一块（复制第 0 块），原来的末块不再是末块（规格测试表）")
    dec("incomplete_extra_block_full", "min_full", [{"op": "append", "hex": ffull[body:body + 80].hex()}], "incomplete", "3.2：全是满块时尾部多一块，原末块用 0x00 去解，失败")
    dec("incomplete_full_truncated_block", "min_full", [{"op": "truncate", "len": len(ffull) - 80}], "incomplete", "3.2：全是满块时去掉末块，截断在块边界，倒数第二块用 0x01 去解，失败")
    dec("incomplete_swap", "min", [{"op": "swap", "a": body, "b": body + 80, "len": 80}], "incomplete", "3.2：交换第 0、1 块，块序号在随机数里（规格测试表）")
    dec("incomplete_flip_block2", "min", [{"op": "xor", "at": body + 2 * 80 + 5, "mask": 0x40}], "incomplete", "3.2：改第 2 块里一个字节（规格测试表）")
    dec("incomplete_flip_tag", "min", [{"op": "xor", "at": len(fmin) - 1, "mask": 1}], "incomplete", "3.2：改末块认证标签的最后一个字节")
    dec("incomplete_other_chunk_size", "min", rep_header(hdr(chunk_size=128)), "incomplete",
        "文件头改成 chunk_size 128（仍合格、密钥对），AAD 变了，而且按 128 切块也不对 → 3.8 第 6 步")
    # 第 7 步
    for n in ["gzip_zeros", "gzip_garbage", "gzip_magic_only", "gzip_bad_crc", "gzip_bad_isize", "gzip_truncated", "gzip_not_gzip"]:
        dec(f"incomplete_{n}", n, [], "incomplete", files[n]["why"])
    # 第 9 步
    dec("corrupt_bom", "none_bom", [], "corrupt", files["none_bom"]["why"])
    dec("corrupt_bad_utf8", "none_bad_utf8", [], "corrupt", files["none_bad_utf8"]["why"])
    dec("corrupt_surrogate_utf8", "none_surrogate_utf8", [], "corrupt", files["none_surrogate_utf8"]["why"])
    dec("ok_manifest9", "manifest9", [], "ok", "decodeBackup 只做到第 9 步，不看清单版本；清单版本由 readManifestDoc（第 10 步）查")
    dec("ok_doc_bad_counts", "doc_bad_counts", [], "ok", "decodeBackup 不查第 4 节的规则")
    dec("incomplete_manifest9_bad_tail", "manifest9", [{"op": "xor", "at": len(fm9) - 1, "mask": 1}], "incomplete",
        "清单 backup-manifest/9，而且末块也坏了 →「坏了或不完整」：3.8 先解完全部块（规格测试表）")

    # ---- read（readBackup：第 1～11 步）
    R = out["read"]

    def rd(name, src, key_input, expect, why, ops=()):
        f = apply_ops(bytes.fromhex(files[src]["hex"]) if src else b"", list(ops))
        r = B.read_backup(f, key_input)
        if expect == "ok":
            assert r["ok"], (name, r)
            exp = {"ok": True, "header": r["header"], "backup": norm(r["backup"])}
        else:
            assert r == {"ok": False, "error": expect}, (name, r)
            exp = {"ok": False, "error": expect}
        R.append({"name": name, "from": src, "ops": list(ops), "keyInput": key_input, "expect": exp, "why": why})

    rd("ok_min", "min", "123456", "ok", "最小文件：清单和 end，各部分都是空的")
    rd("ok_fullwidth_key", "min", "１２３ ４５６", "ok", "3.8 第 1 步按 2.2 规整：全角数字加空格")
    rd("ok_fixture_none", "fixture_none", "123 456", "ok", "样例文件：读出的每一部分和设备 B 的存储一样（收据、导入记录、发布包已按码点排好）")
    rd("ok_gzip_min", "gzip_min", "123456", "ok", "gzip 模式读出来和 none 一样")
    rd("key_not_digits_first", None, "12a456", "key_not_digits", "3.8 第 1 步在第 2 步之前：文件是空的也先报密钥", ops=[])
    rd("key_not_digits_letter_short", "min", "4821O", "key_not_digits", "3.8 第 1 步：2.2 第 3 步在第 4 步之前")
    rd("key_length", "min", "12345", "key_length", "3.8 第 1 步：五位")
    rd("not_curio", None, "123456", "not_curio", "3.8 第 2 步", ops=[{"op": "append", "hex": png.hex()}])
    rd("wrong_key", "min", "123 457", "wrong_key", "3.8 第 5 步")
    rd("update_manifest9", "manifest9", "123456", "update", "3.8 第 10 步：清单 backup-manifest/9 →「请先更新」（规格测试表）")
    rd("update_manifest9_gzip", "manifest9_gzip", "123456", "update", "同上，gzip 模式")
    rd("incomplete_manifest9_bad_tail", "manifest9", "123456", "incomplete", "3.8：先解完全部块，才看清单版本（规格测试表）", ops=[{"op": "xor", "at": len(fm9) - 1, "mask": 1}])
    rd("corrupt_bom", "none_bom", "123456", "corrupt", "3.8 第 9 步")
    rd("corrupt_counts", "doc_bad_counts", "123456", "corrupt", "3.8 第 11 步：counts 不对")

    # ---- build（buildBackup：第 7 节）
    for name, snap, now, comp, why in [
        ("empty_none", empty_snapshot(), T0, "none", "空的存储、none、random 给全零：文件和 files.min 逐字节相同；文件名按 UTC+8：10:30Z → 18:30"),
        ("fixture_none_midnight", fixture_snapshot(), "2026-11-13T16:30:00.000Z", "none", "设备 B 的存储；16:30Z 是本地次日 00:30，文件名 curio-backup-20261114-0030.curio"),
        ("fixture_gzip", fixture_snapshot(), T0, "gzip", "gzip 不要求逐字节，测试只解开比明文"),
    ]:
        doc = B.write_manifest_doc(snap, created_at=now, app_commit="275c460")
        r = B.build_backup(snap, digits=KEY, now=now, random=lambda n: bytes(n), app_commit="275c460", compression=comp, iterations=600000, chunk_size=64)
        assert r["ok"]
        case = {"name": name, "snapshot": snap, "now": now, "appCommit": "275c460", "compression": comp, "iterations": 600000,
                "chunkSize": 64, "random": "zeros", "expect": {"ok": True, "fileName": r["fileName"], "doc_hex": hx(doc)}, "why": why}
        if comp == "none":
            case["expect"]["hex"] = hx(r["bytes"])
        if name == "empty_none":
            assert r["bytes"] == fmin
        out["build"].append(case)
    snap = fixture_snapshot()
    r = B.build_backup(snap, digits=KEY, now=T0, random=lambda n: bytes(n), app_commit="275c460", compression="none")
    d = B.decode_backup(r["bytes"], KEY)
    assert d["header"]["iterations"] == 600000 and d["header"]["chunk_size"] == 1048576
    out["build"].append({"name": "defaults", "snapshot": snap, "now": T0, "appCommit": "275c460", "compression": "none", "random": "zeros",
                         "expect": {"ok": True, "fileName": r["fileName"], "doc_hex": hx(B.write_manifest_doc(snap, created_at=T0, app_commit="275c460")),
                                    "header": {"iterations": 600000, "chunk_size": 1048576}},
                         "why": "不传 iterations、chunkSize：写的程序 v1 固定写 600000 和 1048576（3.1）"})
    bad = fixture_snapshot()
    bad["inbox"].append('{"x":"\ud800"}')
    assert B.build_backup(bad, digits=KEY, now=T0, random=lambda n: bytes(n), app_commit="275c460", compression="none") == {"ok": False, "error": "self_check"}
    out["build"].append({"name": "lone_surrogate", "snapshot": bad, "now": T0, "appCommit": "275c460", "compression": "none", "random": "zeros",
                         "iterations": 600000, "chunkSize": 64, "expect": {"ok": False, "error": "self_check"},
                         "why": "3.7 末条：原文里有单独的代理项 U+D800，写的程序停下，「备份没做成」。错误代码按 backup-api.md 只有 self_check（歧义 7）"})
    return out


# ================================================================ backup-manifest.json
def manifest_vectors():
    H = {"created_at": T0}
    out = {"about": "明文文档（第 4 节；3.8 第 9～11 步）：writeManifestDoc 逐字节，readManifestDoc 的正反例。read 的 header 只用 created_at。",
           "header": H, "write": [], "read": []}

    def w(name, snap, why, created=T0, commit="275c460"):
        doc = B.write_manifest_doc(snap, created_at=created, app_commit=commit)
        out["write"].append({"name": name, "snapshot": snap, "createdAt": created, "appCommit": commit, "expect_hex": hx(doc), "why": why})
        return doc

    w("empty", empty_snapshot(), "只有清单和 end 两行；lines = 1；sha256 是清单那一行（含 \\n）的 SHA-256 = ec81a6f7…（pr-129 第 2 轮）")
    fdoc = w("fixture", fixture_snapshot(), "设备 B：收件表按到达顺序（含冲突原文 X' 和带换行的 E1 原文）；收据按 event_id 码点排序、键按 event_id, recorded_at, source, batch_id 写；"
             "导入记录键按 5.3 的顺序；archive 里的收据也按收据的键顺序；counts = 10/9/1/1/1，lines = 23")
    esc = empty_snapshot()
    esc["inbox"] = ["\x00\x01\x08\x0c\n\r\t\x1f\x7f\u2028\u2029 中文 🚀 \"q\" \\ /"]
    w("escapes", esc, "3.7：只转义 \" \\ 和 U+0000～U+001F：\\b \\f \\n \\r \\t 用短写法，其余 \\u00xx 小写；U+007F、U+2028、U+2029、中文、emoji、/ 原样（JSON.stringify 的行为）")
    sk = empty_snapshot()
    sk["receipts"] = [{"clock_skew_ms": -1200, "batch_id": SYN, "source": "sync", "recorded_at": "2026-11-12T00:00:00.000Z", "event_id": eid(RAW["B1"])}]
    w("negative_integer", sk, "3.7：同步来的收据 clock_skew_ms 可以是负数，写成 -1200")

    def rd(name, doc, expect, why):
        r = B.read_manifest_doc(doc, H)
        if expect == "ok":
            assert r["ok"], (name, r)
            exp = norm(r)
        else:
            assert r == {"ok": False, "error": expect}, (name, r)
            exp = {"ok": False, "error": expect}
        out["read"].append({"name": name, "doc_hex": hx(doc), "expect": exp, "why": why})

    # 用行组装文档，自动算 end（除非指定）
    def doc_of(first, recs, end=None, raw_lines=None):
        body = B.line(first) + b"".join(r if isinstance(r, bytes) else B.line(r) for r in recs)
        if end is None:
            c = first.get("counts", {}) if isinstance(first, dict) else {}
            n = 1 + sum(v for v in c.values() if isinstance(v, int)) if isinstance(c, dict) else 1
            end = {"t": "end", "lines": n, "sha256": hashlib.sha256(body).hexdigest()}
        return body + (end if isinstance(end, bytes) else B.line(end))

    man = lambda **c: {"schema": "backup-manifest/1", "created_at": T0, "learner_id": L, "device_id": DB, "app_commit": "275c460",  # noqa: E731
                       "counts": dict({"inbox": 0, "receipt": 0, "import": 0, "archive": 0, "release": 0}, **c)}
    r1 = {"t": "inbox", "raw": RAW["B1"]}
    rc1 = {"t": "receipt", "v": rc_local("B1", "2026-11-12T01:00:00.500Z")}
    im = {"t": "import", "v": IMPORT_A}
    ar = {"t": "archive", "v": {"kind": "receipt", "v": rc_local("E1", "2026-11-10T08:00:00.200Z")}}
    arI = {"t": "archive", "v": {"kind": "import", "v": IMPORT_A}}
    rl = {"t": "release", "raw": REL1["raw"]}
    full = man(inbox=1, receipt=1, **{"import": 1}, archive=2, release=1)
    good = doc_of(full, [r1, rc1, im, ar, arI, rl])
    rd("ok_fixture", fdoc, "ok", "设备 B 的完整文档")
    rd("ok_all_kinds", good, "ok", "五种记录各有，archive 有 receipt 和 import 两种 kind")
    rd("ok_empty", min_doc(), "ok", "只有清单和 end")
    rd("ok_counts_key_order", doc_of(dict(full, counts={"release": 1, "archive": 2, "import": 1, "receipt": 1, "inbox": 1}), [r1, rc1, im, ar, arI, rl]), "ok",
       "第 4 节：counts 的键要正好是那五个，但读的时候不查顺序（3.7、R40）")
    rd("ok_key_order_and_spaces", doc_of(full, [b'{ "raw" : ' + json.dumps(RAW["B1"]).encode() + b', "t":"inbox" }\n', rc1, im, ar, arI, rl]), "ok",
       "3.7：读的时候不查键的顺序和写法（空格、ASCII 转义），end 的 sha256 按原始字节算")
    rd("corrupt_sha_is_over_raw_bytes", doc_of(man(receipt=1), [{"t": "receipt", "v": {"event_id": eid(RAW["B1"]), "recorded_at": T0, "source": "sync", "batch_id": SYN, "clock_skew_ms": 5}}]).replace(b'"clock_skew_ms":5}', b'"clock_skew_ms":5.0}'), "corrupt",
       "第 4 节：sha256 按解压后的原始字节算，不先解码再编码：把 5 改写成 5.0（值相同）而 end 照旧，sha256 就对不上")
    sk_body = B.line(man(receipt=1)) + b'{"t":"receipt","v":{"event_id":"' + eid(RAW["B1"]).encode() + b'","recorded_at":"' + T0.encode() + b'","source":"sync","batch_id":"' + SYN.encode() + b'","clock_skew_ms":5.0}}\n'
    rd("ok_skew_written_5_0", sk_body + B.line({"t": "end", "lines": 2, "sha256": hashlib.sha256(sk_body).hexdigest()}), "ok",
       "收据的 clock_skew_ms 写成 5.0：读的时候不查写法，值是整数就合格（ingest-receipt 的 integer，JS 读出来就是 5）")
    rd("ok_unsorted_receipts", doc_of(man(receipt=2), [{"t": "receipt", "v": rc_local("B2", T0)}, {"t": "receipt", "v": rc_local("B1", T0)}]), "ok",
       "第 4 节的检查表只对 release 要求排序、不重复；收据的顺序读的时候不查（歧义 9）")
    endbody = B.line(full) + b"".join(B.line(x) for x in [r1, rc1, im, ar, arI, rl])
    rd("ok_end_lines_7_0", endbody + b'{"t":"end","lines":7.0,"sha256":"' + hashlib.sha256(endbody).hexdigest().encode() + b'"}\n', "ok",
       "end 的 lines 写成 7.0：值是整数 7，读的时候不查写法")
    # 第 9 步
    rd("corrupt_bom", b"\xef\xbb\xbf" + min_doc(), "corrupt", "第 4 节：以 BOM 开头（规格测试表）")
    rd("corrupt_bad_utf8", min_doc().replace(b"275c460", b"275c\xc060"), "corrupt", "第 4 节：坏的 UTF-8（C0 是不允许的起始字节）（规格测试表）")
    rd("corrupt_overlong", min_doc().replace(b"275c460", b"275c\xc0\xb060"), "corrupt", "第 4 节：过长编码 C0 B0（严格 UTF-8 不认）")
    rd("corrupt_bad_utf8_before_version", manifest_doc_with({"schema": "backup-manifest/9"}, b"\xff\n"), "corrupt", "3.8：第 9 步在第 10 步之前，清单是 /9 也先看 UTF-8")
    # 第 10 步
    rd("update_manifest9", manifest_doc_with({"schema": "backup-manifest/9", "created_at": T0}, b"garbage\n"), "update", "3.8 第 10 步（规格测试表）")
    rd("update_manifest2_no_newline", B.line({"schema": "backup-manifest/2"})[:-1], "update", "3.8 第 10 步：第一行就是整个文档（没有 \\n）也照样看 schema")
    rd("update_missing_schema", manifest_doc_with({"created_at": T0}), "update", "歧义 3：第一行是 JSON 对象而 schema 不是 backup-manifest/1（这里没有 schema）→ 第 10 步")
    rd("corrupt_first_line_not_json", b"not json\n" + min_doc(), "corrupt", "歧义 3：第一行解析不出 JSON 对象，看不出版本，按第 11 步「坏了」")
    rd("corrupt_first_line_array", b'["backup-manifest/9"]\n', "corrupt", "歧义 3：第一行是数组，不是对象 →「坏了」")
    rd("corrupt_empty", b"", "corrupt", "歧义 3：空文档")
    # 第 11 步：清单
    rd("corrupt_manifest_extra", doc_of(dict(man(), extra=1), []), "corrupt", "第 4 节：清单多一个字段（规格测试表）")
    rd("corrupt_manifest_missing", doc_of({k: v for k, v in man().items() if k != "app_commit"}, []), "corrupt", "第 4 节：清单少 app_commit")
    rd("corrupt_created_at", doc_of(dict(man(), created_at="2026-11-13T10:30:00.001Z"), []), "corrupt", "第 4 节：清单 created_at 和文件头不同（规格测试表）")
    rd("corrupt_learner_id", doc_of(dict(man(), learner_id="lrn_01JC4Y000000000000000000AI"), []), "corrupt", "第 4 节：learner_id 格式不对（I 不在 Crockford 字母表里）（规格测试表）")
    rd("corrupt_learner_id_newline", doc_of(dict(man(), learner_id=L + "\n"), []), "corrupt", "第 4 节：learner_id 末尾带换行，整串匹配不能放过（Python 的 $ 会放过）")
    rd("corrupt_device_id", doc_of(dict(man(), device_id="dev_x"), []), "corrupt", "第 4 节：device_id 格式不对")
    rd("corrupt_app_commit_short", doc_of(dict(man(), app_commit="275c46"), []), "corrupt", "第 4 节：app_commit 只有 6 位")
    rd("corrupt_app_commit_upper", doc_of(dict(man(), app_commit="275C460"), []), "corrupt", "第 4 节：app_commit 有大写")
    rd("ok_app_commit_40", doc_of(dict(man(), app_commit="a" * 40), []), "ok", "第 4 节：40 位可以")
    rd("corrupt_app_commit_41", doc_of(dict(man(), app_commit="a" * 41), []), "corrupt", "第 4 节：41 位不行")
    rd("corrupt_counts_extra_key", doc_of(dict(man(), counts=dict(man()["counts"], text=0)), []), "corrupt", "第 4 节：counts 多一个键")
    rd("corrupt_counts_missing_key", doc_of(dict(man(), counts={k: 0 for k in B.COUNT_KEYS if k != "release"}), []), "corrupt", "第 4 节：counts 少一个键")
    rd("corrupt_counts_negative", doc_of(man(inbox=-1), []).replace(b'"lines":0', b'"lines":1'), "corrupt", "第 4 节：counts 是负数")
    rd("corrupt_counts_fraction", doc_of(man(), []).replace(b'"inbox":0', b'"inbox":0.5'), "corrupt", "第 4 节：counts 不是整数")
    rd("corrupt_counts_wrong", doc_of(man(inbox=2), [r1]), "corrupt", "第 4 节：counts.inbox 是 2，只有 1 行；end 的 lines 照 counts 写成 3（规格测试表「counts 不对」）")
    rd("corrupt_nan", doc_of(man(), []).replace(b'"inbox":0', b'"inbox":NaN'), "corrupt", "JSON 不认 NaN（JSON.parse 拒绝，Python 也不能放过）")
    # 第 11 步：end
    rd("corrupt_end_lines", doc_of(man(inbox=1), [r1], end={"t": "end", "lines": 3, "sha256": hashlib.sha256(B.line(man(inbox=1)) + B.line(r1)).hexdigest()}), "corrupt", "第 4 节：end 的 lines 不对（规格测试表）")
    rd("corrupt_end_sha", doc_of(man(inbox=1), [r1], end={"t": "end", "lines": 2, "sha256": "0" * 64}), "corrupt", "第 4 节：end 的 sha256 不对（规格测试表）")
    rd("corrupt_end_sha_upper", doc_of(man(), [], end={"t": "end", "lines": 1, "sha256": hashlib.sha256(B.line(man())).hexdigest().upper()}), "corrupt", "第 4 节：sha256 要小写")
    rd("corrupt_end_extra", doc_of(man(), [], end={"t": "end", "lines": 1, "sha256": hashlib.sha256(B.line(man())).hexdigest(), "x": 1}), "corrupt", "第 4 节：end 多一个字段")
    rd("corrupt_after_end", min_doc() + B.line(r1), "corrupt", "第 4 节：end 后面还有一行（规格测试表）")
    rd("corrupt_two_ends", min_doc() + min_doc()[-len(B.line({"t": "end", "lines": 1, "sha256": "0" * 64})):], "corrupt", "第 4 节：end 后面又是一个 end")
    rd("corrupt_no_end", B.line(man()), "corrupt", "第 4 节：没有 end 行")
    rd("corrupt_no_trailing_newline", min_doc()[:-1], "corrupt", "第 4 节：最后一行也要以 \\n 结尾")
    rd("corrupt_empty_line", B.line(man()) + b"\n" + min_doc()[len(B.line(man())):], "corrupt", "第 4 节：没有空行")
    rd("corrupt_crlf_extra_line", min_doc().replace(b"}\n{", b"}\n\r\n{"), "corrupt", "第 4 节：中间多一行只有 \\r（不是 JSON 对象）")
    # 第 11 步：记录
    rd("corrupt_order", doc_of(man(inbox=1, receipt=1), [rc1, r1]), "corrupt", "第 4 节：部分的顺序乱了，receipt 在 inbox 前面（规格测试表）")
    rd("corrupt_order_release_archive", doc_of(man(archive=1, release=1), [rl, ar]), "corrupt", "第 4 节：release 在 archive 前面")
    rd("corrupt_unknown_t", doc_of(man(), [{"t": "text", "v": {}}]), "corrupt", "第 4 节：t 只能是那几种")
    rd("corrupt_record_extra", doc_of(man(inbox=1), [dict(r1, x=1)]), "corrupt", "第 4 节：记录行正好两个字段")
    rd("corrupt_inbox_not_string", doc_of(man(inbox=1), [{"t": "inbox", "raw": {"a": 1}}]), "corrupt", "第 4 节：inbox 的 raw 是字符串")
    rd("corrupt_inbox_v", doc_of(man(inbox=1), [{"t": "inbox", "v": RAW["B1"]}]), "corrupt", "第 4 节：inbox 行用 raw，不是 v")
    rd("ok_inbox_garbage_raw", doc_of(man(inbox=1), [{"t": "inbox", "raw": "这不是 JSON"}]), "ok", "第 4 节：raw 的内容这里不查，恢复时交给日志判断")
    rd("corrupt_receipt_schema", doc_of(man(receipt=1), [{"t": "receipt", "v": dict(rc_local("B1", T0), batch_id=IMP_A)}]), "corrupt", "第 4 节：收据不符合 ingest-receipt（local 不能有 batch_id）")
    rd("corrupt_receipt_import_no_batch", doc_of(man(receipt=1), [{"t": "receipt", "v": dict(rc_local("B1", T0), source="import")}]), "corrupt", "ingest-receipt：import 必须有 batch_id")
    rd("corrupt_receipt_sync_no_skew", doc_of(man(receipt=1), [{"t": "receipt", "v": dict(rc_local("B1", T0), source="sync", batch_id=SYN)}]), "corrupt", "ingest-receipt：sync 必须有 clock_skew_ms")
    rd("corrupt_receipt_import_syn", doc_of(man(receipt=1), [{"t": "receipt", "v": dict(rc_local("B1", T0), source="import", batch_id=SYN)}]), "corrupt", "ingest-receipt：import 的 batch_id 是 imp_")
    rd("corrupt_receipt_event_id_newline", doc_of(man(receipt=1), [{"t": "receipt", "v": dict(rc_local("B1", T0), event_id=eid(RAW["B1"]) + "\n")}]), "corrupt",
       "ingest-receipt：event_id 整串匹配（jsonschema 的 pattern 用 re.search，$ 会放过末尾换行；JS 的 $ 不放过。按 JS 和规格的意思判坏）")
    rd("corrupt_receipt_skew_bool", doc_of(man(receipt=1), [{"t": "receipt", "v": {"event_id": eid(RAW["B1"]), "recorded_at": T0, "source": "sync", "batch_id": SYN, "clock_skew_ms": True}}]), "corrupt", "ingest-receipt：clock_skew_ms 是整数，true 不是")
    rd("ok_receipt_sync", doc_of(man(receipt=1), [{"t": "receipt", "v": {"event_id": eid(RAW["B1"]), "recorded_at": T0, "source": "sync", "batch_id": SYN, "clock_skew_ms": -5}}]), "ok", "ingest-receipt：sync 带 syn_ 和 clock_skew_ms（负数可以）")
    rd("corrupt_import_partial", doc_of(man(**{"import": 1}), [{"t": "import", "v": dict(IMPORT_A, partial="no")}]), "corrupt", "5.3：partial 是布尔值")
    rd("corrupt_import_extra", doc_of(man(**{"import": 1}), [{"t": "import", "v": dict(IMPORT_A, note="x")}]), "corrupt", "5.3：不能有别的字段")
    rd("corrupt_import_missing", doc_of(man(**{"import": 1}), [{"t": "import", "v": {k: v for k, v in IMPORT_A.items() if k != "releases"}}]), "corrupt", "5.3：少 releases")
    rd("corrupt_import_negative", doc_of(man(**{"import": 1}), [{"t": "import", "v": dict(IMPORT_A, accepted=-1)}]), "corrupt", "5.3：计数是非负整数")
    rd("corrupt_import_salt", doc_of(man(**{"import": 1}), [{"t": "import", "v": dict(IMPORT_A, file_salt=b64(bytes(15)))}]), "corrupt", "5.3：file_salt 是文件头的 salt，16 字节")
    rd("corrupt_import_source", doc_of(man(**{"import": 1}), [{"t": "import", "v": dict(IMPORT_A, source="legacy")}]), "corrupt", "5.3：source 只有 backup（歧义 8）")
    rd("ok_import_partial", doc_of(man(**{"import": 1}), [{"t": "import", "v": dict(IMPORT_A, partial=True, accepted=0, archived=0)}]), "ok", "5.3：partial: true 的导入记录（点了「不恢复了」）")
    rd("corrupt_archive_kind", doc_of(man(archive=1), [{"t": "archive", "v": {"kind": "text", "v": {}}}]), "corrupt", "第 4 节：archive 的 kind 只能是 receipt 或 import")
    rd("corrupt_archive_inner", doc_of(man(archive=1), [{"t": "archive", "v": {"kind": "import", "v": rc_local("B1", T0)}}]), "corrupt", "第 4 节：kind 是 import，里面却是收据")
    rd("corrupt_archive_extra", doc_of(man(archive=1), [{"t": "archive", "v": {"kind": "receipt", "v": rc_local("B1", T0), "x": 1}}]), "corrupt", "第 4 节：archive 的 v 正好 kind 和 v 两个字段")
    rd("corrupt_release_not_json", doc_of(man(release=1), [{"t": "release", "raw": "{"}]), "corrupt", "第 4 节：发布包原文解析出来是对象")
    rd("corrupt_release_array", doc_of(man(release=1), [{"t": "release", "raw": "[]"}]), "corrupt", "第 4 节：发布包原文解析出来是对象，不是数组")
    bad_rel = dict(json.loads(REL1["raw"]), content_hash="0" * 64)
    rd("corrupt_release_hash", doc_of(man(release=1), [{"t": "release", "raw": json.dumps(bad_rel, indent=2)}]), "corrupt",
       "第 4 节：release_id 不等于 rel_ + content_hash（content_hash 换成 64 个 0）")
    rd("corrupt_release_no_hash", doc_of(man(release=1), [{"t": "release", "raw": json.dumps({"release_id": REL1["release_id"]})}]), "corrupt",
       "第 4 节：没有 content_hash")
    rd("corrupt_release_id_format", doc_of(man(release=1), [{"t": "release", "raw": json.dumps({"release_id": "rel_ABC", "content_hash": "ABC"})}]), "corrupt", "第 4 节：release_id 是 rel_<64 位小写十六进制>")
    rd("corrupt_release_unsorted", doc_of(man(release=2), [{"t": "release", "raw": REL1["raw"]}, {"t": "release", "raw": REL0["raw"]}] if REL1["release_id"] > REL0["release_id"] else
                                         [{"t": "release", "raw": REL0["raw"]}, {"t": "release", "raw": REL1["raw"]}]), "corrupt", "第 4 节：发布包按 release_id 排序")
    rd("corrupt_release_duplicate", doc_of(man(release=2), [rl, rl]), "corrupt", "第 4 节：发布包不重复")
    two = sorted([REL0, REL1], key=lambda r: r["release_id"])
    rd("ok_two_releases", doc_of(man(release=2), [{"t": "release", "raw": two[0]["raw"]}, {"t": "release", "raw": two[1]["raw"]}]), "ok", "第 4 节：两个发布包按 release_id 排好")
    return out


# ================================================================ backup-restore.json
def header_for(created=T0, salt=ZERO16):
    """恢复计划用的文件头：和 decodeBackup 解出来的一样（key_check 照算）。"""
    _, check = B.derive(KEY, salt, 600000)
    return json.loads(B.header_line(created, 600000, salt, check, ZERO7, 64, "none"))


def backup_of(snap, created=T0, salt=ZERO16, commit="275c460"):
    """从一台设备的存储做一份备份，再按 readBackup 读出来：恢复计划拿到的就是这个。"""
    doc = B.write_manifest_doc(snap, created_at=created, app_commit=commit)
    r = B.read_manifest_doc(doc, {"created_at": created})
    assert r["ok"], r
    return {"header": header_for(created, salt), "backup": {k: r[k] for k in ("manifest", *B.COUNT_KEYS)}}


def device(learner, dev, raws=(), receipts=(), nextSeq=1, **kw):
    s = {"identity": {"learner_id": learner, "device_id": dev}, "nextSeq": nextSeq, "inbox": list(raws), "receipts": list(receipts),
         "imports": [], "archive": [], "releases": [], "recoveryKey": None, "restoring": None}
    s.update(kw)
    return s


NOW1, NOW2 = "2026-11-14T03:00:00.000Z", "2026-11-14T04:00:00.000Z"


def restore_vectors():
    out = {"about": "恢复计划 planRestore（6.1、6.2、2.3）。expect 是计划（batches 只写每批的条数和 ownSeqMax，items 就是全部批次按顺序接起来）；"
                    "after 是按计划写完以后的存储（runRestore + 假存储应得到它）；fingerprint_after 是恢复后被接收事件的指纹；"
                    "log_after 是用恢复后的收件表重放得到的日志（接收的 event_id 按接收顺序、隔离区条数）。",
           "cases": []}
    C = out["cases"]

    def case(name, existing, backup, why, batch=IMP_P, now=NOW1, key=KEY, extra_why=None):
        plan = B.plan_restore(copy.deepcopy(existing), copy.deepcopy(backup), batch_id=batch, now=now, input_key=key)
        c = {"name": name, "existing": existing, "backup": backup, "opts": {"batchId": batch, "now": now, "inputKey": key}, "why": why}
        if not plan["ok"]:
            c["expect"] = plan
        else:
            log = plan.pop("_log")
            plan["batches"] = [{"count": len(b["items"]), "ownSeqMax": b["ownSeqMax"]} for b in plan["batches"]]
            c["expect"] = norm(plan)
            after = B.apply_plan(existing, dict(plan, batches=[{"items": plan["items"], "ownSeqMax": max([i.get("own_seq", 0) for i in plan["items"]] or [0])}]))
            c["after"] = dump_store(after)
            relog = B.log_of(after["inbox"])
            assert [e["event_id"] for e in relog.events] == [e["event_id"] for e in log.events]
            c["fingerprint_after"] = B.fingerprint([e["event_id"] for e in relog.events])
            c["log_after"] = {"accepted": [e["event_id"] for e in relog.events], "quarantined": len(relog.quarantined)}
        C.append(c)
        return c

    FIXB = backup_of(fixture_snapshot(), salt=FIX_NONE["salt"], commit=FIX_COMMIT)
    clean = device(LR, DR, releases=[REL0])
    c1 = case("clean_device", clean, FIXB,
              "6.1 第 1 行：干净设备（只有发布包、没有收件表等）恢复别的身份的备份。身份换成 L、device_id 仍是 R；10 条原文按顺序："
              "B1～B5、E1、E2 接收（带 source import 的收据），X' 和 B2 同 ID 不同内容 → 隔离（quarantined_new），B6、B7 接收：accepted 9；"
              "带过来的：收据 9 + 导入记录 1 + archive 1 = 11 条全新，archived 11；发布包 REL1 本机没有，releases 1；"
              "没有本机 R 的事件，nextSeq = max(1, 0+1) = 1；本机没有密钥 → 写 {123456, now}（2.3）。恢复后的日志、指纹和设备 B 一样")
    fp_b = B.fingerprint([e["event_id"] for e in B.log_of(fixture_snapshot()["inbox"]).events])
    assert c1["fingerprint_after"] == fp_b
    c1["why"] += f"（设备 B 的指纹也是 {fp_b}）"
    after1 = c1["after"]
    case("import_twice", after1, FIXB,
         "6.2 末段：同一个文件导入第二次：9 条 duplicate、X' 已在 seenRaw 里 → quarantined_skipped 1；带过来的 11 条比较键都已在本机（receipts、imports、archive）→ 全部跳过；"
         "发布包已有；items 空、nextSeq 不变；密钥已确认且相同 → 不写。只多一条导入记录（batch imp_P2）", batch=IMP_2, now=NOW2)
    x, x2 = RAW["B2"], RAW["X'"]
    small = lambda raws, **kw: backup_of(device(L, DB, raws, nextSeq=1 + len(raws), **kw))  # noqa: E731
    case("x_then_x_prime", device(LR, DR), small([RAW["B1"], x, x2]),
         "6.2 第 3 步：备份里先有 X（B2）、后有同 ID 不同内容的 X'：X 接收、X' 隔离，和原设备一样（到达顺序被保留）；备份里没有收据 → noReceipt 2")
    case("local_has_x_prime", device(L, DR, [RAW["B1"], x2], nextSeq=1), small([RAW["B1"], x]),
         "6.2 第 3 步：本机已有 X'（被接收），备份里有 X：本机的 X' 不动，X 进隔离区（conflict → quarantined_new），items 里只有原文没有收据；B1 重复")
    other_local = device(K, DR, [js(ev("R01", DR, 1, "2026-11-13T00:00:00.000Z", "attempt.started", "T9", {"mode": "first"}, learner=K))], nextSeq=2)
    case("other_learner_with_records", other_local, FIXB, "6.1 第 3 行：本机有记录、learner_id 是 K，备份是 L → 拒绝 other_learner，什么都不写")
    case("other_learner_clean", device(K, DR), FIXB, "6.1 第 1 行：本机是 K 但干净 → 身份换成 L（changeIdentity），device_id 不变")
    case("same_learner_clean", device(L, DR), FIXB, "6.1 第 1 行：干净、learner_id 本来就是 L → 不用换身份（changeIdentity false）")
    case("archive_only_not_clean", device(K, DR, archive=[{"kind": "receipt", "v": rc_local("B1", T0)}]), FIXB,
         "6.1：收件表空、但 archive 不空 → 不算干净；learner 不同 → other_learner（规格测试表）")
    case("imports_only_not_clean", device(K, DR, imports=[IMPORT_A]), FIXB, "6.1：imports 不空 → 不算干净 → other_learner")
    case("receipts_only_not_clean", device(K, DR, receipts=[rc_local("B1", T0)]), FIXB, "6.1：receipts 不空 → 不算干净 → other_learner")
    marker = {"batch_id": IMP_M, "started_at": NOW1, "file_created_at": T0, "file_device_id": DB, "file_salt": b64(FIX_NONE["salt"]), "file_learner_id": L}
    assert B.same_file(marker, FIXB["header"], FIXB["backup"]["manifest"])
    other_child = backup_of(device(K, DE, [js(ev("K01", DE, 1, "2026-11-13T00:00:00.000Z", "attempt.started", "T8", {"mode": "first"}, learner=K))], nextSeq=2))
    case("restoring_other_child", device(L, DR, restoring=marker, recoveryKey={"digits": KEY, "confirmed_at": NOW1}), other_child,
         "6.1 第 4 行：有 restoring，备份是别的孩子（file_learner_id 等都不同）→ other_restore（规格测试表）。本机收件表空也一样：先看 restoring")
    for field, bk, why in [
        ("salt", backup_of(fixture_snapshot(), salt=bytes([1] * 16), commit=FIX_COMMIT), "file_salt 不同（同一台设备、同一时刻的另一个文件也会不同）"),
        ("created_at", backup_of(fixture_snapshot(), created="2026-11-13T10:31:00.000Z", salt=FIX_NONE["salt"], commit=FIX_COMMIT), "file_created_at 不同"),
        ("device", backup_of(dict(fixture_snapshot(), identity={"learner_id": L, "device_id": DE}), salt=FIX_NONE["salt"], commit=FIX_COMMIT), "file_device_id 不同"),
    ]:
        case(f"restoring_other_file_{field}", device(L, DR, [RAW["B1"]], [rc_import("B1", NOW1, IMP_M)], restoring=marker, recoveryKey={"digits": KEY, "confirmed_at": NOW1}), bk,
             f"6.1 第 4 行：有 restoring、同一个孩子，但不是同一个文件：{why} → other_restore（规格测试表「有 restoring 时换另一个文件」）")
    resumed = device(L, DR, [RAW[k] for k in FIX_ORDER[:3]], [rc_import(k, NOW1, IMP_M) for k in FIX_ORDER[:3]], restoring=marker,
                     recoveryKey={"digits": KEY, "confirmed_at": NOW1}, releases=[REL0])
    case("restoring_same_file", resumed, FIXB,
         "6.1：有 restoring 而且是同一个文件 → 照第 2 行合并，沿用标记里的 batch_id imp_M1（参数给的 imp_P1 不用），marker 原样；"
         "已经写进去的 3 条算 duplicate，剩下 7 条（含 X'）补上，收据的 batch_id 也是 imp_M1；身份已经是 L，不换；密钥已确认且相同，不写", batch=IMP_P, now=NOW2)
    b4 = [RAW[k] for k in ["B1", "B2", "B3", "B4"]]
    rb4 = [rc_local(k, f"2026-11-12T01:0{i}:00.500Z") for i, k in enumerate(["B1", "B2", "B3", "B4"])]
    rolled = device(L, DB, b4[:2], rb4[:2], nextSeq=3, recoveryKey={"digits": KEY, "confirmed_at": T0})
    case("own_seq_rollback", rolled, backup_of(device(L, DB, b4, rb4, nextSeq=5)),
         "6.2 第 6 步：备份里有本机 device_id 的 1～4，本机只有 1～2、nextSeq 3：B3、B4 接收并标 own_seq 3、4；nextSeq = max(3, 4+1) = 5，ownEarlier；"
         "批次的 ownSeqMax = 4；B3、B4 的原收据（local）不在本机 → archived 2（规格测试表）")
    nyk = [
        js(ev("N01", DB, 1, T0, "poe.predicted", "T5", {"choice": "a"})),
        js(ev("N02", DB, 2, T0, "dance.started", "T5", {})),
        js(dict(ev("N03", DB, 3, T0, "attempt.started", "T5", {"mode": "first"}), schema="event/3")),
        js(ev("N04", DB, 4, T0, "attempt.started", "T5", {"mode": "first", "speed": 2})),
        "这不是 JSON",
        js(dict(ev("N05", DB, 5, T0, "attempt.started", "T5", {"mode": "first"}), verb=5)),
        "[1,2]",
        js(ev("N06", DB, 6, T0, "poe.predicted", "T5", {"choice": 7, "oops": True})),
        js(dict(ev("N07", DB, 7, T0, "attempt.started", "T5", {"mode": "first"}), schema="event/3")),
        js(dict(ev("N08", DB, 8, T0, "attempt.started", "T5", {"mode": "first"}), schema="evento/2")),
    ]
    nyk.append(nyk[2])
    case("not_yet_known", device(LR, DR), small(nyk),
         "6.2 第 3 步「这一版还不认识的」，planRestore 自己解析判断：poe.predicted（schema 里有、本版不认）、dance.started（schema 里也没有）、event/3、"
         "poe.predicted 的 payload 也不对（规则只看动词，照样算）、另一条 event/3 → not_yet_known 5；attempt.started 的 payload 多一个字段、不是 JSON、"
         "verb 是数字、数组、schema 是 evento/2 → quarantined_new 5；最后一条和第 3 条逐字节相同 → quarantined_skipped 1（规格测试表）")
    r_sync = {"event_id": eid(RAW["B1"]), "recorded_at": "2026-11-12T01:00:00.500Z", "source": "sync", "batch_id": SYN, "clock_skew_ms": 5}
    r_sync_backup = {"clock_skew_ms": 5.0, "batch_id": SYN, "source": "sync", "recorded_at": "2026-11-12T01:00:00.500Z", "event_id": eid(RAW["B1"])}
    imp_reordered = dict(reversed(list(IMPORT_A.items())))
    arch_local = {"kind": "receipt", "v": rc_local("E1", "2026-11-10T08:00:00.200Z")}
    ex13 = device(L, DR, [RAW["B1"]], [r_sync], imports=[IMPORT_A], archive=[arch_local], nextSeq=1)
    bk13 = {"header": header_for(), "backup": {
        "manifest": {"schema": "backup-manifest/1", "created_at": T0, "learner_id": L, "device_id": DB, "app_commit": "275c460",
                     "counts": {"inbox": 1, "receipt": 2, "import": 1, "archive": 2, "release": 0}},
        "inbox": [RAW["B1"]],
        "receipt": [r_sync_backup, dict(r_sync, recorded_at="2026-11-12T01:00:00.600Z")],
        "import": [imp_reordered],
        "archive": [{"kind": "receipt", "v": dict(reversed(list(arch_local["v"].items())))}, {"kind": "import", "v": dict(IMPORT_A, archived=2)}],
        "release": []}}
    case("carried_dedupe", ex13, bk13,
         "6.2 第 4 步：比较键 = kind + \\n + 规范 JSON。带过来的收据和本机的只是键的顺序不同、clock_skew_ms 写成 5.0 → 跳过；导入记录键顺序反了 → 跳过；"
         "archive 里的收据键顺序反了 → 跳过。对照：recorded_at 差 0.1 秒的收据、archived 不同的导入记录 → 是新的，archived 2（规格测试表）")
    selfb = fixture_snapshot()
    case("self_restore", selfb, FIXB,
         "6.2 第 4 步末：用自己的备份恢复自己：收件表 9 条重复、X' 原文已在本机 → 跳过；带过来的全部跳过；发布包已有；items 空、nextSeq 8 不变")
    kbk = small([RAW["B1"]])
    for name, rk, why in [
        ("key_none", None, "本机没有密钥 → 写 {123456, now}"),
        ("key_unconfirmed", {"digits": "654321", "confirmed_at": None}, "本机有密钥但没确认 → 换成输入的 123456，confirmed_at = now"),
        ("key_confirmed_same", {"digits": KEY, "confirmed_at": T0}, "本机已确认且相同 → 不写（recoveryKey null）"),
        ("key_confirmed_other", {"digits": "654321", "confirmed_at": T0}, "本机已确认且不同 → 不覆盖，keyMismatch true；备份照样恢复"),
    ]:
        case(name, device(LR, DR, recoveryKey=rk), kbk, "2.3：恢复开始时（restoreBegin）怎么写密钥：" + why)
    return out


# ================================================================ backup-export.json
def export_vectors():
    out = {"about": "记录指纹（第 8 节）和可读导出（第 9 节）。", "fingerprint": [], "export": []}
    for ids, why in [
        ([], "第 8 节：0 条是空串的 SHA-256 前 8 位 e3b0c442（规格测试表）"),
        ([eid(RAW["B1"])], "第 8 节：一条：SHA-256(event_id + \\n) 的前 8 位"),
        ([eid(RAW[k]) for k in ["B7", "E1", "B1", "B3"]], "第 8 节：按码点排序后再连（E 开头的 ID 排在 B 后面），输入的顺序不影响"),
        ([eid(RAW[k]) for k in ["B1", "B3", "B7", "E1"]], "同上一条，已排好的顺序，指纹相同"),
    ]:
        out["fingerprint"].append({"ids": ids, "expect": B.fingerprint(ids), "why": why})
    assert out["fingerprint"][0]["expect"] == "e3b0c442"
    assert out["fingerprint"][2]["expect"] == out["fingerprint"][3]["expect"]
    t = "2026-11-12T05:00:00.000Z"
    a = js(ev("X10", DE, 10, t, "attempt.started", "T6", {"mode": "first"}))
    b = js(ev("X02", DE, 2, t, "attempt.started", "T7", {"mode": "first"}))
    c = js(ev("X05", DB, 5, t, "attempt.started", "T8", {"mode": "first"}))
    d = js(ev("X01", DB, 1, "2026-11-12T04:00:00.000Z", "attempt.started", "T9", {"mode": "first"}))
    e = '{"schema":"event/2",\r\n "event_id":"evt_' + u("X99") + '","learner_id":"' + L + '","device_id":"' + DB + '",\n"device_seq":9.0,' \
        '"occurred_at":"2026-11-12T06:00:00.000Z","actor":{"type":"learner","id":"' + L + '"},"verb":"attempt.completed","attempt_id":"att_' + u("T9") + '",' \
        '"content":' + js(CONTENT) + ',"payload":{"duration_ms":1.0}}'
    assert B.log_of([e]).events, "e 要是合格的事件"
    for raws, why, ex_at in [
        ([], "第 9 节：0 条：首行 events 0，尾行是首行的 SHA-256", "2026-11-13T15:59:00.000Z"),
        ([e, a, b, c, d], "第 9 节：按排序键 (occurred_at, device_id, device_seq, event_id)：d（04:00）→ c（05:00、dev_…B）→ b（05:00、dev_…E、seq 2）→ a（seq 10，按整数比，不是按字符串）→ e（06:00）；"
         "e 原文里的 \\r\\n 换成两个空格、\\n 换成一个空格，9.0、1.0 原样不改（规格测试表「含一条带换行和 1.0 的原文」）；"
         "文件名按 UTC+8：16:00Z → 次日 00:00", "2026-11-13T16:00:00.000Z"),
    ]:
        r = B.build_export(raws, exported_at=ex_at, learner_id=L)
        out["export"].append({"raws": raws, "exportedAt": ex_at, "learnerId": L, "expect": {"hex": hx(r["bytes"]), "fileName": r["fileName"]}, "why": why})
    return out


# ================================================================ 写出
def safe_dump(obj):
    """ensure_ascii=False，但把看不见的字符（类别 C*、Z*，空格除外）写成 \\uXXXX，免得在编辑器里看不出来。"""
    text = json.dumps(obj, ensure_ascii=False, indent=1)

    def esc(m):
        ch = m.group(0)
        if ord(ch) > 0xFFFF:
            hi, lo = divmod(ord(ch) - 0x10000, 0x400)
            return f"\\u{0xD800 + hi:04x}\\u{0xDC00 + lo:04x}"
        return f"\\u{ord(ch):04x}"
    return re.sub(r"[^\S \n]|[\x7f\u0080-\u00a0\u00ad\u061c\u1680\u180e\u2000-\u200f\u2028-\u202f\u205f-\u206f\u3000\ufeff\ud800-\udfff]", esc, text) + "\n"


def all_vectors():
    return {"backup-key.json": key_vectors(), "backup-file.json": file_vectors(), "backup-manifest.json": manifest_vectors(),
            "backup-restore.json": restore_vectors(), "backup-export.json": export_vectors()}


FIXTURE_FILES = {"v1-none.curio": lambda: fixture_file("none"), "v1-gzip.curio": lambda: fixture_file("gzip")}


def write_all():
    VEC.mkdir(parents=True, exist_ok=True)
    for name, obj in all_vectors().items():
        (VEC / name).write_text(safe_dump(obj), encoding="utf-8")
    FIX.mkdir(parents=True, exist_ok=True)
    for name, make in FIXTURE_FILES.items():
        p = FIX / name
        if p.exists():
            print(f"{p} 已经有了，不覆盖（样例文件是永久的）")
        else:
            p.write_bytes(make())
    p = FIX / "expected-doc.jsonl"
    if not p.exists():
        p.write_bytes(fixture_doc())


# ================================================================ 测试
def load(name):
    return json.loads((VEC / name).read_text(encoding="utf-8"))


def hexb(s):
    return bytes.fromhex(s)


class TestVectorsUpToDate(unittest.TestCase):
    """磁盘上的向量就是参考实现现在算出的结果（改了参考实现或向量，两边要一起改）。"""

    def test_every_vector_file_matches_reference(self):
        for name, obj in all_vectors().items():
            with self.subTest(file=name):
                self.assertEqual(json.loads((VEC / name).read_text(encoding="utf-8")), json.loads(safe_dump(obj)))

    def test_every_case_says_why(self):
        def walk(v, path):
            if isinstance(v, dict):
                if any(k in v for k in ("expect", "expect_hex")):
                    self.assertTrue(str(v.get("why", "")).strip(), f"{path} 没写 why")
                for k, x in v.items():
                    walk(x, f"{path}.{k}")
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{path}[{i}]")
        for name in all_vectors():
            walk(load(name), name)

    def test_no_invisible_characters_in_files(self):
        for p in VEC.glob("backup-*.json"):
            text = p.read_text(encoding="utf-8")
            bad = [hex(ord(c)) for c in text if c not in "\n " and unicodedata.category(c)[0] in "CZ"]
            self.assertEqual(bad, [], p.name)


class TestKey(unittest.TestCase):
    def test_vectors(self):
        v = load("backup-key.json")
        for g in v["generate"]:
            it = iter(g["u32"])
            self.assertEqual(B.generate_key(lambda: next(it)), g["expect"], g["why"])
        for f in v["format"]:
            self.assertEqual(B.format_key(f["digits"]), f["expect"])
        for p in v["parse"]:
            self.assertEqual(B.parse_key(p["input"]), p["expect"], p["why"])

    def test_each_rule_has_pass_and_fail(self):
        res = {json.dumps(p["expect"]["ok"]) + p["expect"].get("error", "") for p in load("backup-key.json")["parse"]}
        self.assertEqual(res, {"true", "falsekey_not_digits", "falsekey_length"})

    def test_rejection_threshold_is_uniform(self):
        """2.1：[0, 4294000000) 里每个余数正好 4294 次。"""
        self.assertEqual(4294000000 % 1000000, 0)
        self.assertEqual(4294000000 // 1000000, 4294)
        self.assertGreater(4294000000 + 1000000, 2**32)

    def test_language_whitespace_would_be_caught(self):
        """用 Python 的 isspace 代替封闭表，至少一条向量对不上。"""
        def variant(s):
            t = "".join(ch for ch in unicodedata.normalize("NFKC", s) if not (ch.isspace() or ch in "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u30fc"))
            if any(ch not in "0123456789" for ch in t):
                return {"ok": False, "error": "key_not_digits"}
            return {"ok": False, "error": "key_length"} if len(t) != 6 else {"ok": True, "digits": t}
        self.assertTrue(any(variant(p["input"]) != p["expect"] for p in load("backup-key.json")["parse"]))

    def test_order_of_checks_would_be_caught(self):
        """先查长度再查数字（2.2 第 3、4 步颠倒），4821O 会报错成 key_length。"""
        p = [x for x in load("backup-key.json")["parse"] if x["input"] == "4821O"][0]
        self.assertEqual(p["expect"]["error"], "key_not_digits")


class TestFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = load("backup-file.json")
        cls.files = {k: hexb(f["hex"]) for k, f in cls.v["files"].items()}

    def test_file_digests(self):
        for k, f in self.v["files"].items():
            self.assertEqual(hashlib.sha256(self.files[k]).hexdigest(), f["sha256"])
            self.assertEqual(len(self.files[k]), f["bytes"])

    def test_min_file_cross_checked_with_node(self):
        """Python 和 Node 22 Web Crypto 各自独立算出的最小文件（交付说明里有 Node 的结果）。"""
        self.assertEqual(self.v["files"]["min"]["sha256"], "80916e4248db01c847bbaed6e2e65f23c159ef5a008eb2e02980924f2ea9183d")
        self.assertEqual(self.v["files"]["min"]["bytes"], 747)
        self.assertEqual(self.v["files"]["min_full"]["sha256"], "2411d3ddd31b0df109503e147098342e3be0673ec0fd2328537e1fabc297799f")

    def test_reviewer_value_at_1000_iterations(self):
        """pr-129 第 3 轮：iterations 1000 时 745 字节、77d96f1f…、key_check EHt8Lz6IA6cPE5AACBHoVg==。"""
        f = B.encode_backup(min_doc(), digits=KEY, created_at=T0, salt=ZERO16, nonce_prefix=ZERO7, iterations=1000, chunk_size=64)
        self.assertEqual(len(f), 745)
        self.assertEqual(hashlib.sha256(f).hexdigest(), "77d96f1fd3bb0d7612cb075816d804cbd230ee00df38c00d2dc80f15d860ab47")
        self.assertIn(b'"key_check":"EHt8Lz6IA6cPE5AACBHoVg=="', f)
        self.assertEqual(B.decode_backup(f, KEY), {"ok": False, "error": "corrupt"}, "读的程序不接受 1000 轮（下限 100000）")

    def test_encode(self):
        for c in self.v["encode"]:
            p = c["params"]
            f = B.encode_backup(hexb(c["doc_hex"]), digits=p["digits"], created_at=p["createdAt"], salt=hexb(p["salt_hex"]),
                                nonce_prefix=hexb(p["noncePrefix_hex"]), iterations=p["iterations"], chunk_size=p["chunkSize"], compression=p["compression"])
            self.assertEqual(f, self.files[c["file"]], c["why"])

    def test_decode(self):
        for c in self.v["decode"]:
            with self.subTest(c["name"]):
                f = apply_ops(self.files[c["from"]] if c["from"] else b"", c["ops"])
                r = B.decode_backup(f, c["digits"], c.get("maxPlain", B.DEFAULT_MAX_PLAIN))
                if r["ok"]:
                    r = {"ok": True, "doc_hex": hx(r["doc"]), "header": r["header"], "headerLine_hex": hx(r["headerLine"])}
                self.assertEqual(r, c["expect"], c["why"])

    def test_every_decode_code_has_a_case(self):
        codes = {c["expect"].get("error", "ok") for c in self.v["decode"]}
        self.assertEqual(codes, {"ok", "not_curio", "update", "corrupt", "wrong_key", "incomplete", "too_big"})

    def test_read(self):
        for c in self.v["read"]:
            with self.subTest(c["name"]):
                f = apply_ops(self.files[c["from"]] if c["from"] else b"", c["ops"])
                r = B.read_backup(f, c["keyInput"])
                if r["ok"]:
                    r = {"ok": True, "header": r["header"], "backup": norm(r["backup"])}
                self.assertEqual(r, c["expect"], c["why"])

    def test_build(self):
        for c in self.v["build"]:
            with self.subTest(c["name"]):
                kw = {k: c[k2] for k, k2 in (("iterations", "iterations"), ("chunk_size", "chunkSize")) if k2 in c}
                r = B.build_backup(c["snapshot"], digits=KEY, now=c["now"], random=lambda n: bytes(n), app_commit=c["appCommit"], compression=c["compression"], **kw)
                if not c["expect"]["ok"]:
                    self.assertEqual(r, c["expect"])
                    continue
                self.assertEqual(r["fileName"], c["expect"]["fileName"])
                if "hex" in c["expect"]:
                    self.assertEqual(hx(r["bytes"]), c["expect"]["hex"])
                d = B.decode_backup(r["bytes"], KEY)
                self.assertEqual(hx(d["doc"]), c["expect"]["doc_hex"])
                for k, v in c["expect"].get("header", {}).items():
                    self.assertEqual(d["header"][k], v)

    def test_wrong_reader_variants_are_caught(self):
        """常见的错误读法要有向量对不上：gzip.decompress（悄悄接受末尾的零）、截断在块边界时不认末块。"""
        import gzip
        stream_ok = hexb(self.v["files"]["gzip_min"]["stream_hex"])
        self.assertEqual(gzip.decompress(stream_ok + b"\x00\x00\x00\x00"), min_doc(), "gzip.decompress 接受末尾的零，所以不能用它")
        self.assertRaises(B.Fail, B.gunzip, stream_ok + b"\x00\x00\x00\x00")
        self.assertEqual(B.gunzip(stream_ok + stream_ok), min_doc() + min_doc())


class TestFixtures(unittest.TestCase):
    """tests/fixtures/backup/ 里的永久样例文件（3.5），以后的读程序必须一直能读它们。"""

    def test_none_fixture_is_byte_exact(self):
        self.assertEqual((FIX / "v1-none.curio").read_bytes(), fixture_file("none"))

    def test_both_fixtures_decode_to_the_same_doc(self):
        doc = (FIX / "expected-doc.jsonl").read_bytes()
        self.assertEqual(doc, fixture_doc())
        for name in FIXTURE_FILES:
            with self.subTest(name):
                d = B.decode_backup((FIX / name).read_bytes(), KEY)
                self.assertTrue(d["ok"], d)
                self.assertEqual(d["doc"], doc)
                self.assertEqual(d["header"]["compression"], name[3:-6])
                self.assertEqual(d["header"]["iterations"], 600000)
                self.assertEqual(d["header"]["chunk_size"], 64)
                self.assertEqual(B.decode_backup((FIX / name).read_bytes(), "654321"), {"ok": False, "error": "wrong_key"})

    def test_gzip_fixture_is_one_member_flg0_mtime0(self):
        f = (FIX / "v1-gzip.curio").read_bytes()
        hs, he = header_bounds(f)
        h = json.loads(f[hs:he])
        enc_key, _ = B.derive(KEY, base64.b64decode(h["salt"]), h["iterations"])
        first = B.AESGCM(enc_key).decrypt(B.nonce(base64.b64decode(h["nonce_prefix"]), 0, False), f[he + 1:he + 1 + 80], f[:he])
        self.assertEqual(first[:4], b"\x1f\x8b\x08\x00")
        self.assertEqual(first[4:8], b"\x00\x00\x00\x00")

    def test_fixture_contents(self):
        r = B.read_backup((FIX / "v1-none.curio").read_bytes(), KEY)
        b = r["backup"]
        self.assertEqual(b["manifest"]["counts"], {"inbox": 10, "receipt": 9, "import": 1, "archive": 1, "release": 1})
        log = B.log_of(b["inbox"])
        self.assertEqual(len(log.events), 9)
        self.assertEqual([q["reason"] for q in log.quarantined], ["conflict"])

    def test_cli_decode(self):
        p = subprocess.run([sys.executable, str(REPO / "tools/backup_ref.py"), "decode", str(FIX / "v1-gzip.curio"), "123 456"], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, fixture_doc())
        p = subprocess.run([sys.executable, str(REPO / "tools/backup_ref.py"), "decode", str(FIX / "v1-none.curio"), "123457"], capture_output=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("wrong_key", p.stderr.decode())
        self.assertEqual(p.stdout, b"")


class TestManifest(unittest.TestCase):
    def test_write(self):
        for c in load("backup-manifest.json")["write"]:
            with self.subTest(c["name"]):
                self.assertEqual(hx(B.write_manifest_doc(c["snapshot"], created_at=c["createdAt"], app_commit=c["appCommit"])), c["expect_hex"], c["why"])

    def test_read(self):
        v = load("backup-manifest.json")
        for c in v["read"]:
            with self.subTest(c["name"]):
                self.assertEqual(norm(B.read_manifest_doc(hexb(c["doc_hex"]), v["header"])), c["expect"], c["why"])

    def test_read_has_pass_and_fail_for_each_part(self):
        names = [c["name"] for c in load("backup-manifest.json")["read"]]
        for part in ["receipt", "import", "release", "manifest", "end", "counts"]:
            self.assertTrue(any(part in n and n.startswith("corrupt") for n in names) or part in ("manifest",), part)
        self.assertTrue(any(n.startswith("ok") for n in names))
        self.assertTrue(any(n.startswith("update") for n in names))

    def test_written_docs_read_back(self):
        for c in load("backup-manifest.json")["write"]:
            r = B.read_manifest_doc(hexb(c["expect_hex"]), {"created_at": c["createdAt"]})
            self.assertTrue(r["ok"], c["name"])
            self.assertEqual(r["inbox"], c["snapshot"]["inbox"])

    def test_escape_line_by_hand(self):
        """3.7 手算：escapes 那一行的收件记录逐字写出来。"""
        c = [x for x in load("backup-manifest.json")["write"] if x["name"] == "escapes"][0]
        lines = hexb(c["expect_hex"]).split(b"\n")
        self.assertEqual(lines[1].decode("utf-8"),
                         '{"t":"inbox","raw":"\\u0000\\u0001\\b\\f\\n\\r\\t\\u001f\x7f\u2028\u2029 中文 🚀 \\"q\\" \\\\ /"}')

    def test_end_line_by_hand(self):
        doc = min_doc()
        first, end = doc.split(b"\n")[:2]
        self.assertEqual(json.loads(end), {"t": "end", "lines": 1, "sha256": hashlib.sha256(first + b"\n").hexdigest()})
        self.assertEqual(json.loads(end)["sha256"], "ec81a6f7475b330b42e02d247c175df40f399af4a06fde4156929264178e26b1")


class TestRestorePlan(unittest.TestCase):
    def test_cases(self):
        for c in load("backup-restore.json")["cases"]:
            with self.subTest(c["name"]):
                p = B.plan_restore(copy.deepcopy(c["existing"]), copy.deepcopy(c["backup"]), batch_id=c["opts"]["batchId"], now=c["opts"]["now"], input_key=c["opts"]["inputKey"])
                if not p["ok"]:
                    self.assertEqual(p, c["expect"])
                    continue
                p.pop("_log")
                p["batches"] = [{"count": len(b["items"]), "ownSeqMax": b["ownSeqMax"]} for b in p["batches"]]
                self.assertEqual(norm(p), c["expect"], c["why"])

    def test_coverage(self):
        names = {c["name"] for c in load("backup-restore.json")["cases"]}
        need = {"clean_device", "import_twice", "x_then_x_prime", "local_has_x_prime", "other_learner_with_records", "other_learner_clean",
                "archive_only_not_clean", "restoring_other_child", "restoring_same_file", "own_seq_rollback", "not_yet_known", "carried_dedupe",
                "self_restore", "key_none", "key_unconfirmed", "key_confirmed_same", "key_confirmed_other"}
        self.assertEqual(need - names, set())

    def test_hand_counts(self):
        """几条手算的计数（why 里写的），独立于参考实现再核一遍。"""
        cs = {c["name"]: c for c in load("backup-restore.json")["cases"]}
        r = cs["clean_device"]["expect"]["record"]
        self.assertEqual([r[k] for k in B.IMPORT_COUNTS], [9, 0, 0, 1, 0, 11, 1])
        r = cs["import_twice"]["expect"]
        self.assertEqual(r["items"], [])
        self.assertEqual([r["record"][k] for k in B.IMPORT_COUNTS], [0, 9, 0, 0, 1, 0, 0])
        r = cs["not_yet_known"]["expect"]["record"]
        self.assertEqual((r["not_yet_known"], r["quarantined_new"], r["quarantined_skipped"]), (5, 5, 1))
        r = cs["own_seq_rollback"]["expect"]
        self.assertEqual((r["nextSeq"], r["report"]["ownEarlier"], r["batches"]), (5, True, [{"count": 4, "ownSeqMax": 4}]))
        self.assertEqual(cs["carried_dedupe"]["expect"]["record"]["archived"], 2)
        self.assertEqual(cs["self_restore"]["expect"]["items"], [])
        self.assertEqual(cs["restoring_same_file"]["expect"]["batchId"], IMP_M)
        self.assertEqual(cs["key_confirmed_other"]["expect"]["keyMismatch"], True)
        self.assertEqual(cs["other_learner_with_records"]["expect"], {"ok": False, "reason": "other_learner"})

    def test_log_matches_reflog(self):
        """backup_ref.Log 和 tools/tests/test_vectors.py 的 RefLog 对全部内核向量给出同样的结论。"""
        import test_vectors as TV
        for name, v in TV.vectors():
            ref, mine = TV.RefLog(), B.Log()
            for item in v["inputs"]:
                raw = TV.raw_of(v, item)
                r = mine.ingest(raw)
                self.assertEqual(r[0] if r[0] != "quarantined" else "quarantined:" + r[1], ref.ingest(raw), name)


class TestExport(unittest.TestCase):
    def test_vectors(self):
        v = load("backup-export.json")
        for c in v["fingerprint"]:
            self.assertEqual(B.fingerprint(c["ids"]), c["expect"], c["why"])
        for c in v["export"]:
            r = B.build_export(c["raws"], exported_at=c["exportedAt"], learner_id=c["learnerId"])
            self.assertEqual({"hex": hx(r["bytes"]), "fileName": r["fileName"]}, c["expect"], c["why"])

    def test_export_by_hand(self):
        c = load("backup-export.json")["export"][1]
        lines = hexb(c["expect"]["hex"]).split(b"\n")
        self.assertEqual(lines[-1], b"")
        self.assertEqual(json.loads(lines[-2]), {"sha256": hashlib.sha256(b"".join(x + b"\n" for x in lines[:-2])).hexdigest()})
        ids = [json.loads(x)["event_id"][-3:] for x in lines[1:-2]]
        self.assertEqual(ids, ["X01", "X05", "X02", "X10", "X99"])
        self.assertIn(b'{"schema":"event/2",   "event_id"', lines[5])
        self.assertIn(b'"device_seq":9.0', lines[5])
        self.assertEqual(c["expect"]["fileName"], "curio-export-20261114-0000.jsonl")


class TestImportRecordSchema(unittest.TestCase):
    def test_schema(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((REPO / "schemas/import-record.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        val = Draft202012Validator(schema)
        self.assertTrue(val.is_valid(IMPORT_A))
        for bad in [dict(IMPORT_A, partial="no"), dict(IMPORT_A, extra=1), {k: v for k, v in IMPORT_A.items() if k != "file_salt"},
                    dict(IMPORT_A, accepted=-1), dict(IMPORT_A, accepted=1.5), dict(IMPORT_A, batch_id="syn_" + u("A1")),
                    dict(IMPORT_A, file_salt=b64(bytes(15))), dict(IMPORT_A, schema="import-record/2"), dict(IMPORT_A, source="sync"),
                    dict(IMPORT_A, file_salt="AAAAAAAAAAAAAAAAAAAAAB==")]:
            with self.subTest(bad=bad):
                self.assertFalse(val.is_valid(bad))
                self.assertFalse(B._import_ok(bad))

    def test_schema_agrees_with_reference_on_every_vector_record(self):
        from jsonschema import Draft202012Validator
        val = Draft202012Validator(json.loads((REPO / "schemas/import-record.schema.json").read_text(encoding="utf-8")))
        recs = [c["expect"]["record"] for c in load("backup-restore.json")["cases"] if c["expect"]["ok"]]
        recs += [i for c in load("backup-restore.json")["cases"] for i in c["existing"]["imports"]]
        self.assertGreater(len(recs), 10)
        for r in recs:
            self.assertTrue(val.is_valid(r) and B._import_ok(r), r)


class TestReceiptCheck(unittest.TestCase):
    def test_hand_check_agrees_with_schema(self):
        from jsonschema import Draft202012Validator
        val = Draft202012Validator(json.loads((REPO / "schemas/ingest-receipt.schema.json").read_text(encoding="utf-8")))
        base = rc_local("B1", T0)
        cases = [base, dict(base, source="import", batch_id=IMP_A), dict(base, source="sync", batch_id=SYN, clock_skew_ms=-3),
                 dict(base, batch_id=IMP_A), dict(base, source="import"), dict(base, source="sync", batch_id=SYN),
                 dict(base, source="import", batch_id=SYN), dict(base, x=1), dict(base, source="cloud"), dict(base, recorded_at="x"),
                 dict(base, source="sync", batch_id=SYN, clock_skew_ms=1.5), dict(base, source="import", batch_id=IMP_A, clock_skew_ms=0)]
        for c in cases:
            with self.subTest(c=c):
                self.assertEqual(B._receipt_ok(c), val.is_valid(c))


if __name__ == "__main__":
    if "--write" in sys.argv:
        write_all()
        print("写好了：", ", ".join(sorted(all_vectors())))
    else:
        unittest.main()
