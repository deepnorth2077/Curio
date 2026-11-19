#!/usr/bin/env python3
"""Curio 备份格式的 Python 参考实现（docs/specs/backup.md 第 4 稿）。

两个用途：
1. 黄金向量（app/vectors/backup-*.json）和样例文件（tests/fixtures/backup/）的期望值从这里算出来，
   浏览器实现（app/backup.js、app/restore.js）照它们验收。这份代码不看任何 JS 实现。
2. 「十年后不靠 Curio 也能解开」：只用 Python 标准库加 cryptography 包。

    python tools/backup_ref.py decode <文件.curio> <6 位数字>

把解密、解压以后的明文清单（JSON Lines）原样写到标准输出；读不了时在标准错误里写结论代码和给家长的话，退出码 1。

除了 plan_restore 用到的事件日志（要 jsonschema 和仓库里的 schemas/event.schema.json，用到时才导入），
其余函数都不依赖仓库里的别的文件。
"""
import base64
import hashlib
import json
import re
import struct
import sys
import unicodedata
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

FORMAT = "curio-backup/1"
MANIFEST = "backup-manifest/1"
EXPORT = "curio-export/1"
WRITE_ITERATIONS = 600000
WRITE_CHUNK_SIZE = 1048576
MAGIC = b"CURIO-BACKUP/"
LINE1 = b"CURIO-BACKUP/1\n"
MAX_HEADER = 4096
DEFAULT_MAX_PLAIN = 1 << 30

MESSAGES = {
    "key_not_digits": "恢复密钥只有数字",
    "key_length": "恢复密钥是 6 个数字",
    "not_curio": "这不是 Curio 的备份文件",
    "update": "这个备份是新版本的 Curio 做的，请先更新 Curio",
    "corrupt": "备份文件坏了",
    "wrong_key": "恢复密钥不对。请对照纸上的密钥再输一次",
    "incomplete": "备份文件坏了，或者不完整。换一个备份文件试试",
    "too_big": "备份太大，这台设备放不下",
}

ULID = "[0-7][0-9A-HJKMNP-TV-Z]{25}"
RE_LRN = re.compile(f"lrn_{ULID}")
RE_DEV = re.compile(f"dev_{ULID}")
RE_EVT = re.compile(f"evt_{ULID}")
RE_IMP = re.compile(f"imp_{ULID}")
RE_SYN = re.compile(f"syn_{ULID}")
RE_TS = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{3}Z")
RE_COMMIT = re.compile(r"[0-9a-f]{7,40}")
RE_REL = re.compile(r"rel_[0-9a-f]{64}")
RE_HEX64 = re.compile(r"[0-9a-f]{64}")

HEADER_KEYS = ["format", "created_at", "kdf", "iterations", "salt", "key_check", "cipher", "nonce_prefix", "chunk_size", "compression"]
COUNT_KEYS = ["inbox", "receipt", "import", "archive", "release"]
MANIFEST_KEYS = ["schema", "created_at", "learner_id", "device_id", "app_commit", "counts"]
RECEIPT_KEYS = ["event_id", "recorded_at", "source", "batch_id", "clock_skew_ms"]
IMPORT_KEYS = ["schema", "batch_id", "imported_at", "source", "partial", "file_created_at", "file_device_id", "file_salt",
               "accepted", "duplicate", "not_yet_known", "quarantined_new", "quarantined_skipped", "archived", "releases"]
IMPORT_COUNTS = IMPORT_KEYS[8:]
EXPORT_NOTE = "每行一条学习事件，格式见 Curio 仓库 docs/specs/events.md。最后一行是前面所有行的 SHA-256。"

# 2.2 第 2 步：封闭的表，不用语言自带的「空白」定义
STRIP = set("\t\n\x0b\x0c\r  　-‐‑‒–—―−ー")


class Fail(Exception):
    """读不下去：code 是 3.8 的结论代码。"""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class WriteError(Exception):
    """写的程序出错（3.7 末条：单独的代理项等），做备份时停下。"""


# ---------------------------------------------------------------- 2. 恢复密钥
def generate_key(next_u32):
    """2.1：x ≥ 4294000000 丢掉重取，否则 x mod 10^6 补零到 6 位。"""
    while True:
        x = next_u32()
        if not (isinstance(x, int) and 0 <= x < 2**32):
            raise ValueError("next_u32 要给 0..2^32-1 的整数")
        if x < 4294000000:
            return f"{x % 1000000:06d}"


def format_key(digits):
    return digits[:3] + " " + digits[3:]


def parse_key(s):
    """2.2：NFKC → 去掉封闭表里的字符 → 只许 0～9 → 正好 6 个。"""
    t = unicodedata.normalize("NFKC", s)
    t = "".join(ch for ch in t if ch not in STRIP)
    if any(ch not in "0123456789" for ch in t):
        return {"ok": False, "error": "key_not_digits"}
    if len(t) != 6:
        return {"ok": False, "error": "key_length"}
    return {"ok": True, "digits": t}


# ---------------------------------------------------------------- 3.7 JSON 行的写法
def ints(v):
    """写之前把整数值的数写成整数（3.7：这些行里的数都是整数）。布尔值不动。"""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, float):
        if v.is_integer():
            return int(v)
        raise WriteError("这些行里的数只能是整数")
    if isinstance(v, dict):
        return {k: ints(x) for k, x in v.items()}
    if isinstance(v, list):
        return [ints(x) for x in v]
    return v


def line(obj):
    """3.7 的写法：不加空格，非 ASCII 原样，只转义 \" \\ 和 U+0000～U+001F（短写法或小写 \\u00xx）。"""
    text = json.dumps(ints(obj), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    try:
        return text.encode("utf-8") + b"\n"
    except UnicodeEncodeError as e:  # 单独的代理项
        raise WriteError("字符串里有单独的代理项") from e


def ordered(obj, keys):
    """按表格的顺序排键；没有的字段不写，表外的字段（不该有）排在后面。"""
    out = {k: obj[k] for k in keys if k in obj}
    for k in obj:
        if k not in out:
            out[k] = obj[k]
    return out


def canonical(v):
    """3.7 末尾的规范 JSON：键按码点排序，整数值写成整数。"""
    if v is None or isinstance(v, bool):
        return json.dumps(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        raise ValueError("比较键里不该有非整数")
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(canonical(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical(v[k]) for k in sorted(v)) + "}"
    raise TypeError(type(v))


def _no_constants(name):
    raise ValueError(f"{name} 不是合法 JSON")


def loads(text):
    """严格的 JSON 解析：不认 NaN、Infinity（和 JSON.parse 一样）。"""
    return json.loads(text, parse_constant=_no_constants)


def is_int(v):
    """JSON 里的整数值。JS 读 5.0 得到 5，所以整数值的小数也算（读的时候不查写法，3.7）。"""
    if isinstance(v, bool):
        return False
    return isinstance(v, int) or (isinstance(v, float) and v.is_integer())


def is_nonneg_int(v):
    return is_int(v) and v >= 0


def full(rx, v):
    return isinstance(v, str) and rx.fullmatch(v) is not None


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


def b64(b):
    return base64.b64encode(b).decode("ascii")


def b64_exact(s, n):
    """标准 Base64、带补位、规范写法，解码后正好 n 字节。不对返回 None。"""
    if not isinstance(s, str):
        return None
    try:
        raw = base64.b64decode(s.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        return None
    if len(raw) != n or b64(raw) != s:
        return None
    return raw


def local_stamp(utc):
    """文件名用的本地时间（UTC+8）：YYYYMMDD-HHMM。"""
    t = datetime.strptime(utc, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc) + timedelta(hours=8)
    return t.strftime("%Y%m%d-%H%M")


# ---------------------------------------------------------------- 3.2 密钥和加密
_KEYS = {}


def derive(digits, salt, iterations):
    """→ (加密密钥 32 字节, key_check 16 字节)。PBKDF2-HMAC-SHA256 → HKDF-SHA256（空 salt）。"""
    k = (digits, bytes(salt), iterations)
    if k not in _KEYS:
        prk = hashlib.pbkdf2_hmac("sha256", digits.encode("ascii"), bytes(salt), iterations, 32)
        enc = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"", info=b"curio-backup/1 enc").derive(prk)
        check = HKDF(algorithm=hashes.SHA256(), length=16, salt=b"", info=b"curio-backup/1 check").derive(prk)
        _KEYS[k] = (enc, check)
    return _KEYS[k]


def header_line(created_at, iterations, salt, key_check, nonce_prefix, chunk_size, compression):
    h = {"format": FORMAT, "created_at": created_at, "kdf": "pbkdf2-sha256+hkdf-sha256", "iterations": iterations,
         "salt": b64(salt), "key_check": b64(key_check), "cipher": "aes-256-gcm", "nonce_prefix": b64(nonce_prefix),
         "chunk_size": chunk_size, "compression": compression}
    return line(h)[:-1]


def nonce(prefix, i, last):
    return bytes(prefix) + struct.pack(">I", i) + (b"\x01" if last else b"\x00")


def gzip_member(data, level=9):
    """3.3 写：一个成员，FLG=0，MTIME=0（XFL 写 0，OS 写 255）。"""
    c = zlib.compressobj(level, zlib.DEFLATED, -15)
    body = c.compress(data) + c.flush()
    return b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff" + body + struct.pack("<II", zlib.crc32(data), len(data) & 0xFFFFFFFF)


def gunzip(data):
    """3.3 读：一个或多个首尾相接的成员；每个成员 CRC32、ISIZE 对；最后一个之后不能再有字节。"""
    out = []
    while True:
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            out.append(d.decompress(data))
            out.append(d.flush())
        except zlib.error:
            raise Fail("incomplete")
        if not d.eof:
            raise Fail("incomplete")
        rest = d.unused_data
        if not rest:
            return b"".join(out)
        if rest[:2] != b"\x1f\x8b":
            raise Fail("incomplete")
        data = rest


def encrypt_stream(stream, *, digits, created_at, salt, nonce_prefix, iterations, chunk_size, compression):
    """把已经按 compression 处理好的字节流切块加密，组成文件。测试用它造多成员 gzip 之类的流。"""
    if not stream:
        raise WriteError("明文流不能是空的")
    enc, check = derive(digits, salt, iterations)
    head = header_line(created_at, iterations, salt, check, nonce_prefix, chunk_size, compression)
    aad = LINE1 + head
    aes = AESGCM(enc)
    chunks = [stream[i:i + chunk_size] for i in range(0, len(stream), chunk_size)]
    if len(chunks) > 2**32 - 1:
        raise WriteError("块太多")
    body = b"".join(aes.encrypt(nonce(nonce_prefix, i, i == len(chunks) - 1), c, aad) for i, c in enumerate(chunks))
    return LINE1 + head + b"\n" + body


def encode_backup(doc, *, digits, created_at, salt, nonce_prefix, iterations=WRITE_ITERATIONS,
                  chunk_size=WRITE_CHUNK_SIZE, compression="none"):
    stream = gzip_member(doc) if compression == "gzip" else bytes(doc)
    return encrypt_stream(stream, digits=digits, created_at=created_at, salt=salt, nonce_prefix=nonce_prefix,
                          iterations=iterations, chunk_size=chunk_size, compression=compression)


def _first_line(file):
    """3.8 第 2、3 步。返回第二行开始的位置。"""
    if len(file) < 15 or file[:13] != MAGIC:
        raise Fail("not_curio")
    i = 13
    while i < len(file) and 0x30 <= file[i] <= 0x39:
        i += 1
    digits = file[13:i]
    if not digits or digits[:1] == b"0" or i >= len(file) or file[i] != 0x0A:
        raise Fail("not_curio")
    if digits != b"1":
        raise Fail("update")
    return i + 1


def parse_header(raw):
    """3.8 第 4 步：长度已经查过；是 JSON 对象、值对、写法对。返回 (header, salt, key_check, nonce_prefix)。"""
    try:
        h = loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Fail("corrupt")
    if not isinstance(h, dict):
        raise Fail("corrupt")
    if h.get("format") != FORMAT or h.get("kdf") != "pbkdf2-sha256+hkdf-sha256" or h.get("cipher") != "aes-256-gcm":
        raise Fail("corrupt")
    if not full(RE_TS, h.get("created_at")):
        raise Fail("corrupt")
    it = h.get("iterations")
    if not (isinstance(it, int) and not isinstance(it, bool) and 100000 <= it <= 10000000):
        raise Fail("corrupt")
    salt = b64_exact(h.get("salt"), 16)
    check = b64_exact(h.get("key_check"), 16)
    prefix = b64_exact(h.get("nonce_prefix"), 7)
    if salt is None or check is None or prefix is None:
        raise Fail("corrupt")
    cs = h.get("chunk_size")
    if not (isinstance(cs, int) and not isinstance(cs, bool) and 64 <= cs <= 16777216 and cs & (cs - 1) == 0):
        raise Fail("corrupt")
    if h.get("compression") not in ("gzip", "none"):
        raise Fail("corrupt")
    if line({k: h.get(k) for k in HEADER_KEYS})[:-1] != raw:  # 写法对：按表的顺序和 3.7 重写，逐字节相同
        raise Fail("corrupt")
    return h, salt, check, prefix


def decode_backup(file, digits, max_plain=DEFAULT_MAX_PLAIN):
    """3.8 第 2～9 步。→ {ok: True, header, headerLine, doc} 或 {ok: False, error}。"""
    try:
        return _decode(bytes(file), digits, max_plain)
    except Fail as f:
        return {"ok": False, "error": f.code}


def _decode(file, digits, max_plain):
    start = _first_line(file)
    nl = file.find(b"\n", start, start + MAX_HEADER + 1)  # 第二行的第 4097 个字节还不是 \n 就是坏了
    if nl < 0:
        raise Fail("corrupt")
    raw_head = file[start:nl]
    h, salt, check, prefix = parse_header(raw_head)
    enc, mine = derive(digits, salt, h["iterations"])
    if mine != check:
        raise Fail("wrong_key")
    aad = file[:nl]
    body = file[nl + 1:]
    cs = h["chunk_size"]
    full_len = cs + 16
    if not body:
        raise Fail("incomplete")
    aes = AESGCM(enc)
    out, pos, i = [], 0, 0
    while pos < len(body):
        rest = len(body) - pos
        if rest > full_len:
            n, last = full_len, False
        else:
            n, last = rest, True
            if n < 17:
                raise Fail("incomplete")
        if i > 2**32 - 2:
            raise Fail("incomplete")
        try:
            out.append(aes.decrypt(nonce(prefix, i, last), body[pos:pos + n], aad))
        except InvalidTag:
            raise Fail("incomplete")
        pos += n
        i += 1
    stream = b"".join(out)
    doc = gunzip(stream) if h["compression"] == "gzip" else stream
    if max_plain is not None and len(doc) > max_plain:
        raise Fail("too_big")
    _utf8(doc)
    return {"ok": True, "header": h, "headerLine": raw_head, "doc": doc}


def _utf8(doc):
    """3.8 第 9 步：严格 UTF-8，不以 BOM 开头。"""
    try:
        text = doc.decode("utf-8")
    except UnicodeDecodeError:
        raise Fail("corrupt")
    if text.startswith("﻿"):
        raise Fail("corrupt")
    return text


# ---------------------------------------------------------------- 4. 明文文档
def _receipt_ok(v):
    """schemas/ingest-receipt.schema.json，手写一遍（整串匹配；整数值的小数也算整数，和 JS 读出来一样）。"""
    if not isinstance(v, dict) or not set(v) <= set(RECEIPT_KEYS):
        return False
    if not {"event_id", "recorded_at", "source"} <= set(v):
        return False
    if not full(RE_EVT, v["event_id"]) or not full(RE_TS, v["recorded_at"]):
        return False
    src = v["source"]
    if "batch_id" in v and not (full(RE_IMP, v["batch_id"]) or full(RE_SYN, v["batch_id"])):
        return False
    if "clock_skew_ms" in v and not is_int(v["clock_skew_ms"]):
        return False
    if src == "local":
        return "batch_id" not in v and "clock_skew_ms" not in v
    if src == "sync":
        return full(RE_SYN, v.get("batch_id")) and "clock_skew_ms" in v
    if src == "import":
        return full(RE_IMP, v.get("batch_id")) and "clock_skew_ms" not in v
    return False


def _import_ok(v):
    """5.3 import-record/1（和 schemas/import-record.schema.json 一致）。"""
    if not isinstance(v, dict) or set(v) != set(IMPORT_KEYS):
        return False
    return (v["schema"] == "import-record/1" and full(RE_IMP, v["batch_id"]) and full(RE_TS, v["imported_at"])
            and v["source"] == "backup" and isinstance(v["partial"], bool) and full(RE_TS, v["file_created_at"])
            and full(RE_DEV, v["file_device_id"]) and b64_exact(v["file_salt"], 16) is not None
            and all(is_nonneg_int(v[k]) for k in IMPORT_COUNTS))


def _release_id(raw):
    """发布包原文 → release_id；不合格返回 None。"""
    if not isinstance(raw, str):
        return None
    try:
        r = loads(raw)
    except ValueError:
        return None
    if not isinstance(r, dict):
        return None
    rid, h = r.get("release_id"), r.get("content_hash")
    if not full(RE_REL, rid) or not isinstance(h, str) or rid != "rel_" + h:
        return None
    return rid


def write_manifest_doc(snapshot, *, created_at, app_commit):
    """第 4 节：snapshot（store.snapshot() 的形状）→ 明文文档字节。"""
    ident = snapshot["identity"]
    receipts = sorted(snapshot["receipts"], key=lambda r: r["event_id"])
    imports = sorted(snapshot["imports"], key=lambda r: r["batch_id"])
    releases = sorted(snapshot["releases"], key=lambda r: r["release_id"])
    archive = snapshot["archive"]
    counts = {"inbox": len(snapshot["inbox"]), "receipt": len(receipts), "import": len(imports),
              "archive": len(archive), "release": len(releases)}
    out = [line({"schema": MANIFEST, "created_at": created_at, "learner_id": ident["learner_id"],
                 "device_id": ident["device_id"], "app_commit": app_commit, "counts": counts})]
    out += [line({"t": "inbox", "raw": r}) for r in snapshot["inbox"]]
    out += [line({"t": "receipt", "v": ordered(r, RECEIPT_KEYS)}) for r in receipts]
    out += [line({"t": "import", "v": ordered(r, IMPORT_KEYS)}) for r in imports]
    out += [line({"t": "archive", "v": {"kind": a["kind"], "v": ordered(a["v"], RECEIPT_KEYS if a["kind"] == "receipt" else IMPORT_KEYS)}})
            for a in archive]
    out += [line({"t": "release", "raw": r["raw"]}) for r in releases]
    body = b"".join(out)
    return body + line({"t": "end", "lines": 1 + sum(counts.values()), "sha256": sha256_hex(body)})


def manifest_version_says_update(doc_text):
    """3.8 第 10 步（本参考实现的读法，见交付说明的歧义 3）：第一行解析成 JSON 对象，而且 schema 不是 backup-manifest/1。"""
    first = doc_text.split("\n", 1)[0]
    try:
        m = loads(first)
    except ValueError:
        return False
    return isinstance(m, dict) and m.get("schema") != MANIFEST


def read_manifest_doc(doc, header):
    """第 4 节的读和全部检查（3.8 第 9～11 步）。"""
    try:
        return _read_doc(bytes(doc), header)
    except Fail as f:
        return {"ok": False, "error": f.code}


def _read_doc(doc, header):
    text = _utf8(doc)
    if manifest_version_says_update(text):
        raise Fail("update")
    if not doc.endswith(b"\n"):
        raise Fail("corrupt")
    raws = doc.split(b"\n")[:-1]
    if any(r == b"" for r in raws):
        raise Fail("corrupt")
    objs = []
    for r in raws:
        try:
            o = loads(r.decode("utf-8"))
        except ValueError:
            raise Fail("corrupt")
        if not isinstance(o, dict):
            raise Fail("corrupt")
        objs.append(o)
    m = objs[0]
    if set(m) != set(MANIFEST_KEYS) or m["schema"] != MANIFEST or m["created_at"] != header["created_at"]:
        raise Fail("corrupt")
    if not full(RE_LRN, m["learner_id"]) or not full(RE_DEV, m["device_id"]) or not full(RE_COMMIT, m["app_commit"]):
        raise Fail("corrupt")
    c = m["counts"]
    if not isinstance(c, dict) or set(c) != set(COUNT_KEYS) or not all(is_nonneg_int(c[k]) for k in COUNT_KEYS):
        raise Fail("corrupt")
    if len(objs) < 2:
        raise Fail("corrupt")
    end = objs[-1]
    if end.get("t") != "end" or set(end) != {"t", "lines", "sha256"}:
        raise Fail("corrupt")
    records = objs[1:-1]
    part = {"inbox": [], "receipt": [], "import": [], "archive": [], "release": []}
    rank = -1
    for o in records:
        t = o.get("t")
        if t not in part:
            raise Fail("corrupt")  # 包括第二个 end（end 后面还有东西）
        r = COUNT_KEYS.index(t)
        if r < rank:
            raise Fail("corrupt")
        rank = r
        if t in ("inbox", "release"):
            if set(o) != {"t", "raw"} or not isinstance(o["raw"], str):
                raise Fail("corrupt")
            part[t].append(o["raw"])
        else:
            if set(o) != {"t", "v"}:
                raise Fail("corrupt")
            v = o["v"]
            if t == "receipt" and not _receipt_ok(v):
                raise Fail("corrupt")
            if t == "import" and not _import_ok(v):
                raise Fail("corrupt")
            if t == "archive":
                if not isinstance(v, dict) or set(v) != {"kind", "v"} or v["kind"] not in ("receipt", "import"):
                    raise Fail("corrupt")
                if not (_receipt_ok if v["kind"] == "receipt" else _import_ok)(v["v"]):
                    raise Fail("corrupt")
            part[t].append(v)
    for k in COUNT_KEYS:
        if len(part[k]) != c[k]:
            raise Fail("corrupt")
    ids = [_release_id(r) for r in part["release"]]
    if any(i is None for i in ids) or any(a >= b for a, b in zip(ids, ids[1:])):
        raise Fail("corrupt")
    if not is_int(end["lines"]) or end["lines"] != 1 + sum(c[k] for k in COUNT_KEYS):
        raise Fail("corrupt")
    body = b"".join(r + b"\n" for r in raws[:-1])
    if not full(RE_HEX64, end["sha256"]) or end["sha256"] != sha256_hex(body):
        raise Fail("corrupt")
    return {"ok": True, "manifest": m, **part}


def read_backup(file, key_input, max_plain=DEFAULT_MAX_PLAIN):
    """3.8 第 1～11 步。"""
    k = parse_key(key_input)
    if not k["ok"]:
        return {"ok": False, "error": k["error"]}
    d = decode_backup(file, k["digits"], max_plain)
    if not d["ok"]:
        return d
    r = read_manifest_doc(d["doc"], d["header"])
    if not r["ok"]:
        return r
    return {"ok": True, "header": d["header"], "backup": {k2: r[k2] for k2 in ("manifest", *COUNT_KEYS)}}


def build_backup(snapshot, *, digits, now, random, app_commit, compression, iterations=WRITE_ITERATIONS,
                 chunk_size=WRITE_CHUNK_SIZE):
    """第 7 节：写文件并在内存里读一遍。random(n) 给 n 个字节（先 salt 后 nonce_prefix）。"""
    try:
        doc = write_manifest_doc(snapshot, created_at=now, app_commit=app_commit)
    except WriteError:
        return {"ok": False, "error": "self_check"}
    salt, prefix = random(16), random(7)
    file = encode_backup(doc, digits=digits, created_at=now, salt=salt, nonce_prefix=prefix, iterations=iterations,
                         chunk_size=chunk_size, compression=compression)
    d = decode_backup(file, digits, None)
    if not d["ok"] or d["doc"] != doc or not read_manifest_doc(d["doc"], d["header"])["ok"]:
        return {"ok": False, "error": "self_check"}
    return {"ok": True, "bytes": file, "fileName": f"curio-backup-{local_stamp(now)}.curio"}


# ---------------------------------------------------------------- 8、9. 指纹和可读导出
def fingerprint(event_ids):
    return sha256_hex("".join(i + "\n" for i in sorted(event_ids)).encode("utf-8"))[:8]


def sort_key(raw):
    e = loads(raw)
    return (e["occurred_at"], e["device_id"], e["device_seq"], e["event_id"])


def build_export(accepted_raws, *, exported_at, learner_id):
    rows = sorted(accepted_raws, key=sort_key)
    out = [line({"format": EXPORT, "exported_at": exported_at, "learner_id": learner_id, "events": len(rows), "note": EXPORT_NOTE})]
    out += [r.replace("\r", " ").replace("\n", " ").encode("utf-8") + b"\n" for r in rows]
    body = b"".join(out)
    return {"bytes": body + line({"sha256": sha256_hex(body)}), "fileName": f"curio-export-{local_stamp(exported_at)}.jsonl"}


# ---------------------------------------------------------------- 6. 恢复计划
SLICE_VERBS = ("attempt.started", "item.answered", "hint.used", "answer.revealed", "attempt.completed", "attempt.abandoned")
_VALIDATOR = None


def _validator():
    global _VALIDATOR
    if _VALIDATOR is None:
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/event.schema.json").read_text(encoding="utf-8"))
        _VALIDATOR = Draft202012Validator(schema)
    return _VALIDATOR


def _numbers(v):
    if isinstance(v, bool):
        return
    if isinstance(v, (int, float)):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _numbers(x)
    elif isinstance(v, list):
        for x in v:
            yield from _numbers(x)


def _number_ok(x):
    x = float(x)
    if x != x or x in (float("inf"), float("-inf")):
        return False
    if x == int(x):
        return abs(x) <= 2**53 - 1
    if abs(x) >= 1e9:
        return False
    mant, _, exp = repr(x).partition("e")
    places = len(mant.partition(".")[2]) - (int(exp) if exp else 0)
    return places <= 6


def same(a, b):
    """事件规格 5.2 的语义相同。"""
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


GRADER = re.compile(r"[a-z][a-z0-9-]*/[1-9][0-9]*")


class Log:
    """内存日志，规则同 kernel/js/log.js 和 tools/tests/test_vectors.py 的 RefLog（测试核对两者一致）。"""

    def __init__(self):
        self.by_id, self.by_seq, self.events, self.raws, self.quarantined = {}, {}, [], [], []

    def _judge(self, raw):
        if not isinstance(raw, str) or len(raw.encode("utf-8", "surrogatepass")) > 16384:
            return ("quarantined", "invalid"), None
        try:
            e = loads(raw)
        except ValueError:
            return ("quarantined", "invalid"), None
        if not isinstance(e, dict) or not all(_number_ok(x) for x in _numbers(e)):
            return ("quarantined", "invalid"), None
        if not _validator().is_valid(e) or e["verb"] not in SLICE_VERBS:
            return ("quarantined", "invalid"), None
        p = e["payload"]
        if e["verb"] == "attempt.started" and "grader" in p:
            g = p["grader"]
            if not (isinstance(g, str) and len(g) <= 32 and GRADER.fullmatch(g)):
                return ("quarantined", "invalid"), None
        old = self.by_id.get(e["event_id"])
        if old is not None:
            return (("duplicate", None) if same(old, e) else ("quarantined", "conflict")), None
        if (e["device_id"], e["device_seq"]) in self.by_seq:
            return ("quarantined", "conflict"), None
        return ("accepted", None), e

    def check(self, raw):
        return self._judge(raw)[0]

    def ingest(self, raw):
        r, e = self._judge(raw)
        if r[0] == "accepted":
            self.by_id[e["event_id"]] = e
            self.by_seq[(e["device_id"], e["device_seq"])] = e["event_id"]
            self.events.append(e)
            self.raws.append(raw)
        elif r[0] == "quarantined":
            self.quarantined.append({"raw": raw, "reason": r[1]})
        return r


def log_of(raws):
    log = Log()
    for r in raws:
        log.ingest(r)
    return log


def not_yet_known(raw):
    """6.2 第 3 步：「这一版还不认识的」。调用前已知 log 判它 invalid。"""
    try:
        e = loads(raw)
    except ValueError:
        return False
    if not isinstance(e, dict):
        return False
    s = e.get("schema")
    if not (isinstance(s, str) and s.startswith("event/")):
        return False
    v = e.get("verb")
    return s != "event/2" or (isinstance(v, str) and v not in SLICE_VERBS)


def _clean(ex):
    return not ex["inbox"] and not ex["receipts"] and not ex["imports"] and not ex["archive"] and not ex["restoring"]


def same_file(marker, header, manifest):
    return (marker["file_created_at"] == header["created_at"] and marker["file_device_id"] == manifest["device_id"]
            and marker["file_salt"] == header["salt"] and marker["file_learner_id"] == manifest["learner_id"])


def ckey(kind, v):
    return kind + "\n" + canonical(v)


BATCH = 500


def plan_restore(existing, backup_in, *, batch_id, now, input_key):
    header, backup = backup_in["header"], backup_in["backup"]
    man = backup["manifest"]
    ident = existing["identity"]
    restoring = existing.get("restoring")
    # 1. 6.1：先看 restoring，再看干净不干净
    if restoring:
        if not same_file(restoring, header, man):
            return {"ok": False, "reason": "other_restore"}
        marker = dict(restoring)
        batch_id = restoring["batch_id"]
        identity, change = dict(ident), False
    else:
        marker = {"batch_id": batch_id, "started_at": now, "file_created_at": header["created_at"],
                  "file_device_id": man["device_id"], "file_salt": header["salt"], "file_learner_id": man["learner_id"]}
        if _clean(existing):
            identity = {"learner_id": man["learner_id"], "device_id": ident["device_id"]}
            change = identity["learner_id"] != ident["learner_id"]
        elif man["learner_id"] == ident["learner_id"]:
            identity, change = dict(ident), False
        else:
            return {"ok": False, "reason": "other_learner"}
    # 2.3：恢复密钥
    rk = existing.get("recoveryKey")
    key_mismatch = False
    if rk is None or rk.get("confirmed_at") is None:
        new_key = {"digits": input_key, "confirmed_at": now}
    else:
        new_key = None
        key_mismatch = rk["digits"] != input_key
    # 2.
    log = log_of(existing["inbox"])
    seen = set(existing["inbox"])
    me = ident["device_id"]
    n = dict.fromkeys(IMPORT_COUNTS, 0)
    items, accepted_ids = [], []
    # 3. 收件
    for raw in backup["inbox"]:
        res, why = log.check(raw)
        if res == "accepted":
            log.ingest(raw)
            e = log.events[-1]
            item = {"inbox": raw, "receipt": {"event_id": e["event_id"], "recorded_at": now, "source": "import", "batch_id": batch_id}}
            if e["device_id"] == me:
                item["own_seq"] = int(e["device_seq"])
            items.append(item)
            accepted_ids.append(e["event_id"])
            n["accepted"] += 1
        elif res == "duplicate":
            n["duplicate"] += 1
        else:
            if raw in seen:
                n["quarantined_skipped"] += 1
                continue
            log.ingest(raw)
            items.append({"inbox": raw})
            seen.add(raw)
            if why == "invalid" and not_yet_known(raw):
                n["not_yet_known"] += 1
            else:
                n["quarantined_new"] += 1
    # 4. 带过来的
    keys = {ckey("receipt", r) for r in existing["receipts"]} | {ckey("import", r) for r in existing["imports"]}
    keys |= {ckey(a["kind"], a["v"]) for a in existing["archive"]}
    carried = [("receipt", v) for v in backup["receipt"]] + [("import", v) for v in backup["import"]]
    carried += [(a["kind"], a["v"]) for a in backup["archive"]]
    for kind, v in carried:
        k = ckey(kind, v)
        if k in keys:
            continue
        keys.add(k)
        items.append({"archive": {"kind": kind, "v": v}})
        n["archived"] += 1
    # 5. 发布包
    have = {r["release_id"] for r in existing["releases"]}
    for raw in backup["release"]:
        rid = _release_id(raw)
        if rid not in have:
            have.add(rid)
            items.append({"release": {"release_id": rid, "raw": raw}})
            n["releases"] += 1
    # 6. nextSeq
    own = [int(e["device_seq"]) for e in log.events if e["device_id"] == me]
    next_seq = max(existing["nextSeq"], (max(own) + 1) if own else 1)
    # 7.
    record = {"schema": "import-record/1", "batch_id": batch_id, "imported_at": now, "source": "backup", "partial": False,
              "file_created_at": header["created_at"], "file_device_id": man["device_id"], "file_salt": header["salt"], **n}
    receipted = {r["event_id"] for r in backup["receipt"]} | {r["event_id"] for r in existing["receipts"]}
    receipted |= {a["v"]["event_id"] for a in list(backup["archive"]) + list(existing["archive"]) if a["kind"] == "receipt"}
    report = {**n, "fingerprint": None, "ownEarlier": next_seq > existing["nextSeq"],
              "noReceipt": sum(1 for i in accepted_ids if i not in receipted)}
    batches = []
    for s in range(0, len(items), BATCH):
        part = items[s:s + BATCH]
        batches.append({"items": part, "ownSeqMax": max([i.get("own_seq", 0) for i in part] or [0])})
    return {"ok": True, "batchId": batch_id, "marker": marker, "identity": identity, "changeIdentity": change,
            "recoveryKey": new_key, "keyMismatch": key_mismatch, "items": items, "batches": batches, "nextSeq": next_seq,
            "record": record, "report": report, "_log": log}


def apply_plan(existing, plan):
    """把一份计划写完以后的存储（restoreBegin → 全部 restoreBatch → restoreEnd），snapshot 的形状。"""
    s = json.loads(json.dumps(existing))
    if not s.get("restoring"):
        if plan["changeIdentity"]:
            s["identity"] = dict(plan["identity"])
        if plan["recoveryKey"] is not None:
            s["recoveryKey"] = dict(plan["recoveryKey"])
    for b in plan["batches"]:
        for it in b["items"]:
            if "inbox" in it:
                s["inbox"].append(it["inbox"])
                if "receipt" in it:
                    s["receipts"] = [r for r in s["receipts"] if r["event_id"] != it["receipt"]["event_id"]] + [it["receipt"]]
            elif "archive" in it:
                s["archive"].append(it["archive"])
            else:
                if all(r["release_id"] != it["release"]["release_id"] for r in s["releases"]):
                    s["releases"].append(it["release"])
        s["nextSeq"] = max(s["nextSeq"], b["ownSeqMax"] + 1)
    s["imports"] = [r for r in s["imports"] if r["batch_id"] != plan["record"]["batch_id"]] + [plan["record"]]
    s["restoring"] = None
    return s


# ---------------------------------------------------------------- 命令行
def main(argv):
    if len(argv) != 4 or argv[1] != "decode":
        sys.stderr.write("用法：python tools/backup_ref.py decode <文件.curio> <6 位数字>\n")
        return 2
    file = Path(argv[2]).read_bytes()
    k = parse_key(argv[3])
    if not k["ok"]:
        sys.stderr.write(f"{k['error']}：{MESSAGES[k['error']]}\n")
        return 1
    d = decode_backup(file, k["digits"], None)
    if not d["ok"]:
        sys.stderr.write(f"{d['error']}：{MESSAGES[d['error']]}\n")
        return 1
    # 解得开就把明文原样写出来；第 4 节的检查不通过（例如以后的清单版本）只在标准错误里提一句，退出码 3
    sys.stdout.buffer.write(d["doc"])
    sys.stdout.buffer.flush()
    r = read_manifest_doc(d["doc"], d["header"])
    if not r["ok"]:
        sys.stderr.write(f"明文检查没通过：{r['error']}：{MESSAGES[r['error']]}\n")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
