#!/usr/bin/env python3
"""恢复密钥的纸条丢了：拿自己的一个备份文件，把 6 位数字一个个试回来（docs/specs/backup.md 第 12 节）。

    python tools/recover_key.py <自己的备份文件.curio>
    python tools/recover_key.py <文件> --jobs 8            # 用 8 个核一起试（默认用这台电脑的全部核）
    python tools/recover_key.py <文件> --from 300000 --to 599999   # 只试一段（可以分几台电脑、分几次试）

只读这一个本机文件，不联网，不写任何文件。找到了在标准输出打印密钥（两组：482 105），退出码 0；
这一段里没有，退出码 1；不是 Curio 的备份文件、或者文件头坏了，退出码 2。

怎么试：读文件头（第一行和第二行，和 tools/backup_ref.py 同一套检查），对每个候选数字用 backup_ref 的派生
（PBKDF2-SHA256 放慢、再 HKDF）算出 key_check，和文件头里的比。不去解密文。每试一个都要做一次 PBKDF2
（v1 写 600000 轮），所以单核大约一天多，多核电脑几个小时。中途按 Ctrl+C 停下，标准错误里的进度
告诉你试到哪里了，下次用 --from 接着试。
"""
import argparse
import multiprocessing
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backup_ref as B  # noqa: E402

CHUNK = 64  # 每个工作进程一次拿多少个候选


def read_header(file):
    """→ (salt, key_check, iterations)。不是 Curio 文件、版本不认识、文件头坏了时抛 B.Fail。"""
    start = B._first_line(file)
    nl = file.find(b"\n", start, start + B.MAX_HEADER + 1)
    if nl < 0:
        raise B.Fail("corrupt")
    h, salt, check, _prefix = B.parse_header(file[start:nl])
    return salt, check, h["iterations"]


def key_check(digits, salt, iterations):
    """backup_ref 的派生；用完清掉它的缓存，试一百万个数也不占内存。"""
    _enc, check = B.derive(digits, salt, iterations)
    B._KEYS.clear()
    return check


def _try_range(args):
    lo, hi, salt, check, iterations = args
    for i in range(lo, hi):
        d = f"{i:06d}"
        if key_check(d, salt, iterations) == check:
            return d
    return None


def search(file, start=0, end=999999, jobs=None, progress=None):
    """在 start..end（含两头）里找。→ 6 位数字的字符串，或者 None。progress(试完的个数, 总数) 可选。"""
    salt, check, iterations = read_header(file)
    if not (0 <= start <= end <= 999999):
        raise ValueError("范围要在 0 到 999999 之间，而且 from 不大于 to")
    total = end - start + 1
    tasks = [(lo, min(lo + CHUNK, end + 1), salt, check, iterations) for lo in range(start, end + 1, CHUNK)]
    jobs = max(1, jobs or os.cpu_count() or 1)
    if jobs == 1:
        done = 0
        for t in tasks:
            found = _try_range(t)
            done += t[1] - t[0]
            if progress:
                progress(done, total)
            if found:
                return found
        return None
    with multiprocessing.Pool(jobs) as pool:
        done = 0
        for t, found in zip(tasks, pool.imap(_try_range, tasks)):
            done += t[1] - t[0]
            if progress:
                progress(done, total)
            if found:
                pool.terminate()
                return found
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description="恢复密钥丢了：用自己的备份文件把 6 位数字试回来（不联网）。")
    p.add_argument("file", help="自己的 .curio 备份文件")
    p.add_argument("--from", dest="start", type=int, default=0, help="从这个数开始试（默认 0）")
    p.add_argument("--to", dest="end", type=int, default=999999, help="试到这个数为止，含它（默认 999999）")
    p.add_argument("--jobs", type=int, default=None, help="同时用几个核（默认全部）")
    p.add_argument("--quiet", action="store_true", help="不打印进度")
    a = p.parse_args(argv)
    try:
        file = Path(a.file).read_bytes()
    except OSError as e:
        sys.stderr.write(f"读不了这个文件：{e}\n")
        return 2
    t0 = time.time()
    last = [0.0]

    def progress(done, total):
        now = time.time()
        if a.quiet or (now - last[0] < 10 and done < total):
            return
        last[0] = now
        rate = done / max(now - t0, 1e-9)
        left = (total - done) / rate if rate else 0
        sys.stderr.write(f"已经试了 {done}/{total}（{done * 100 // total}%），试到 {a.start + done - 1:06d}，大约还要 {left / 3600:.1f} 小时\n")

    try:
        found = search(file, a.start, a.end, a.jobs, progress)
    except B.Fail as f:
        sys.stderr.write(f"{B.MESSAGES[f.code]}\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"{e}\n")
        return 2
    if found:
        sys.stdout.write(f"找到了。恢复密钥是 {B.format_key(found)}\n")
        return 0
    sys.stderr.write(f"在 {a.start:06d} 到 {a.end:06d} 之间没有找到。\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
