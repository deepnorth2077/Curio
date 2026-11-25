# 备份格式的永久样例文件（`curio-backup/1`）

规格：`docs/specs/backup.md` 第 3.5 节。这些文件**永远不改、不删**：以后每一版 Curio 的读程序都必须还能读它们（ADR-006 第 4 条）。出 `curio-backup/2` 时另加新文件，这里的留着。

| 文件 | 说明 |
| --- | --- |
| `v1-none.curio` | `compression: none`。逐字节由 `tools/backup_ref.py` 确定（`tools/tests/test_backup_ref.py` 每次重算核对）。SHA-256 `d2779cba062273f9970120fe491324287f206de77747728f86eee87f860d5eb7`，12905 字节 |
| `v1-gzip.curio` | `compression: gzip`，Python 的 `zlib` 压缩（一个成员，FLG=0、MTIME=0）。gzip 不要求逐字节，所以只核对能解开、明文和 `expected-doc.jsonl` 相同。SHA-256 `b52d2fdd21431ddafd533c38cebd07d1f467f1f9bc37ce7ba825f42633c59e61`，2092 字节 |
| `expected-doc.jsonl` | 两个文件解开以后的明文（`backup-manifest/1`），10077 字节，SHA-256 `67f57a12080e350c11696ce51584ff8987cb427b61ecea5d9a3f76efc0fdc410` |

## 参数

- 恢复密钥：公开的测试密钥 **`123456`**（规格 2.1）。
- `iterations` 600000，`chunk_size` 64，`created_at` `2026-11-13T10:30:00.000Z`。
- `v1-none.curio`：`salt` = 字节 `00 01 … 0f`，`nonce_prefix` = `a0 a1 … a6`。
- `v1-gzip.curio`：`salt` = 字节 `10 11 … 1f`，`nonce_prefix` = `b0 b1 … b6`。
- 清单：`learner_id` `lrn_01JC4Y0000000000000000000A`，`device_id`（做备份的设备 B）`dev_01JC4Y0000000000000000000B`，`app_commit` `d08341b`。

## 里面有什么

设备 B 上一个孩子的记录（`counts`：inbox 10、receipt 9、import 1、archive 1、release 1）：

- **收件表 10 条原文，按到达顺序**：
  - B 的 1～5：一次做完的挑战（`attempt.started` 带 `grader`、答对一题、答错一题带 `misconception`、`answer.revealed`、`attempt.completed`）；
  - E 的 1～2：以前从另一台设备 E 的备份恢复进来的一次尝试。E1 的原文是别的程序写的，记号之间有换行和空格（检查 `raw` 里的 `\n` 照 3.7 转义）；
  - **X'**：和 B2 同一个 `event_id`、`response` 不同 → 被隔离的冲突原文，原样保留；
  - B 的 6～7：没做完的一次尝试，B7 的作答是中文「二分之一」。
  - 重放以后接收 9 条、隔离 1 条（冲突），记录指纹 `58b38d6c`。
- **收据 9 条**：B1～B7 是 `local`；E1、E2 是 `import`（批次 `imp_01JC4Y0000000000000000A1`）。按 `event_id` 的码点顺序。
- **导入记录 1 条**：那次从 E 的备份恢复（`imp_…A1`，accepted 2、archived 1）。
- **archive 1 条**：从 E 的备份带过来的 E1 的 `local` 收据。
- **发布包 1 个**：一个 `release/1` 的 `release.json` 原文（缩进写法、结尾带换行）。

## 不靠 Curio 解开

只要 Python 3 和 `cryptography` 包：

```bash
python tools/backup_ref.py decode tests/fixtures/backup/v1-gzip.curio 123456 > 明文.jsonl
```

格式写在 `docs/specs/backup.md` 第 3、4 节；`tools/backup_ref.py` 的 `decode_backup` 照 3.8 的顺序一步步读，不到 300 行，可以照着用别的语言重写。

## 怎么来的

`python tools/tests/test_backup_ref.py --write`（已经存在的样例文件不会被覆盖）。
