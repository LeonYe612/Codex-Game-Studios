#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doc_dedup_guard.py — 文档去重治理工具（WFGameAI-bugfix）

解决痛点：生成流水线 / agent 会话过度产出文档，且内容大量重复。

三大能力（对应三层机制）：
  - ssot   : 双源守卫。列出 docs/ 与 deliverables/ 的同名(basename)碰撞，
             违反「docs/ 为唯一权威(SSOT)、deliverables/ 只读归档」铁律时硬阻断。
  - gate   : 止血闸门（Layer A）。给定候选新文档，与既有语料逐篇比对近似度，
             超阈值则判定为「应更新既有文档而非新建」，退出码 1 阻断落盘。
  - scan   : 存量清算（Layer B）。对 docs/ + deliverables/ 全量两两比对，
             聚类近似重复，输出人类可读报告 + JSON，供人工合并清算。

相似度算法：
  - scan / gate / write 用 Python 标准库 difflib.SequenceMatcher（整篇字符级比率）。
    difflib 离线、零依赖、确定性，对 66 篇文档两两比对耗时 < 数秒。
  - jscan 用 jscpd 做 markdown **块级**克隆检测（更细：跨文件重复段落），见下。

jscpd 适配器说明（实测，2026-07-28）：
  - `npx jscpd` 默认装 v5 Rust 二进制，markdown 名义注册、实质 0 文件 → 不可用。
  - 已锁定 **jscpd@4.2.5（JS 系）** 于 scripts/jscpd/（markdown 内建可用）。
    jscan 子命令调用该二进制；若缺失会明确报错并给出 `cd scripts/jscpd && npm install`。

用法：
  python3 scripts/doc_dedup_guard.py ssot [--docs DIR] [--deliverables DIR]
  python3 scripts/doc_dedup_guard.py gate <candidate.md> --corpus DIR [--threshold 0.90]
  python3 scripts/doc_dedup_guard.py scan [--docs DIR] [--deliverables DIR] \
         [--threshold 0.75] [--md OUT.md] [--json OUT.json]
  python3 scripts/doc_dedup_guard.py jscan [--docs DIR] [--deliverables DIR] \
         [--min-tokens 15] [--min-lines 3] [--md OUT.md] [--json OUT.json]
  python3 scripts/doc_dedup_guard.py compare [--docs DIR] [--deliverables DIR]

退出码：ssot/gate 发现违规 → 1；scan 永远 0（仅报告，不阻断）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import shutil
import difflib
import subprocess
import tempfile
import datetime
import re

# ---------------------------------------------------------------------------
# 默认阈值（可在命令行覆盖）
#   scan 0.75：低阈值，尽量把疑似冗余都捞出来供人工复核（Layer B 清算）。
#   gate 0.90：高阈值，仅阻断近乎雷同的新文档，避免误伤合法新文档（Layer A 止血）。
# ---------------------------------------------------------------------------
DEFAULT_SCAN_THRESHOLD = 0.75
DEFAULT_GATE_THRESHOLD = 0.90


def _repo_root() -> str:
    """定位仓库根目录：基于调用者当前目录（cwd）的 git toplevel。

    优先用 cwd 解析（用户在哪个项目目录执行，就作用于哪个仓库）；
    仅在 git 不可用时回退到脚本两级上层（scripts/ 在仓库根下），
    保障从历史仓库内 scripts/ 直接调用时的兜底。
    """
    cwd = os.getcwd()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def _iter_md(root: str):
    """递归产出 root 下所有 .md 文件的绝对路径。

    排除项（不计入治理）：
      - deliverables/_archive/ ：已归档的旧副本，允许与 docs/ 同名共存，不视为碰撞。
      - _dedup_report.*       ：本工具自身生成的清算报告，避免自引用污染扫描。
    """
    for dp, _, fns in os.walk(root):
        if "_archive" in dp.split(os.sep):
            continue
        for fn in sorted(fns):
            if fn.endswith(".md") and not fn.startswith("_dedup_report"):
                yield os.path.join(dp, fn)


def _normalize(text: str) -> str:
    """归一化：去每行首尾空白、去空行、转小写，凸显内容级重复（忽略标题/缩进格式差异）。"""
    lines = [ln.strip().lower() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def _similarity(a: str, b: str) -> float:
    """内容级近似度 [0,1]。"""
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


# ---------------------------------------------------------------------------
# 头部日期契约（2026-10-30 用户裁定，与 scripts/docs_index.py::meta_missing 同口径）
# ---------------------------------------------------------------------------
_META_HEAD_LINES = 20
_META_CREATE = re.compile(r"(?:创建|建立|Created|created)\s*[:：]\s*(20\d{2}-\d{2}-\d{2})")
_META_UPDATE = re.compile(r"(?:更新|Update|updated|最后修改|last\s*-?\s*update)\s*[:：]\s*(20\d{2}-\d{2}-\d{2})")


def _ensure_meta(text: str) -> str:
    """确保文本头部（前 _META_HEAD_LINES 行）含「创建日期」「更新日期」；缺则注入。

    注入格式：`> 创建：YYYY-MM-DD` / `> 更新：YYYY-MM-DD`（单行 blockquote）。
    已有 H1 标题时注入到其后；无标题则置于文首。日期取当天。
    """
    lines = text.splitlines()
    head = "\n".join(lines[:_META_HEAD_LINES])
    missing_create = not _META_CREATE.search(head)
    missing_update = not _META_UPDATE.search(head)
    if not missing_create and not missing_update:
        return text

    today = datetime.date.today().isoformat()
    meta_lines = []
    if missing_create:
        meta_lines.append("> 创建：{}".format(today))
    if missing_update:
        meta_lines.append("> 更新：{}".format(today))

    # 找第一个 H1（# 开头）作为注入点；否则文首
    idx = next((i for i, l in enumerate(lines[: _META_HEAD_LINES]) if l.startswith("# ")), None)
    if idx is None:
        # 文首注入：meta 行 + 空行 + 原文
        return "\n".join(meta_lines + ["", text]).rstrip("\n") + "\n"

    # H1 之后插入（H1、空行、meta、空行、剩余）；原文 H1 后若已是空行则不重复
    out = lines[: idx + 1] + [""] + meta_lines
    rest = lines[idx + 1 :]
    if rest:
        out += [""]
        if rest[0] == "":
            out += rest[1:]
        else:
            out += rest
    return "\n".join(out).rstrip("\n") + "\n"



# ---------------------------------------------------------------------------
# 子命令：ssot —— 双源碰撞守卫
# ---------------------------------------------------------------------------
def cmd_ssot(args) -> int:
    docs = args.docs
    deliver = args.deliverables
    d_map: dict[str, list[str]] = {}
    v_map: dict[str, list[str]] = {}
    root = _repo_root()
    if getattr(args, "staged", False):
        prefixes = [os.path.relpath(path, root).replace(os.sep, "/").rstrip("/") + "/"
                    for path in (docs, deliver)]
        staged = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--", *prefixes],
            capture_output=True, check=True,
        ).stdout.split(b"\0")
        for raw in staged:
            if not raw:
                continue
            rel = os.fsdecode(raw)
            name = os.path.basename(rel)
            if not name.endswith(".md") or name.startswith("_dedup_report") or "_archive" in rel.split("/"):
                continue
            for prefix, target in zip(prefixes, (d_map, v_map)):
                if rel.startswith(prefix):
                    target.setdefault(name, []).append(rel)
                    break
    else:
        for p in _iter_md(docs):
            d_map.setdefault(os.path.basename(p), []).append(os.path.relpath(p, root))
        for p in _iter_md(deliver):
            v_map.setdefault(os.path.basename(p), []).append(os.path.relpath(p, root))

    collisions = sorted(set(d_map) & set(v_map))
    if not collisions:
        print("[ssot] OK：docs/ 与 deliverables/ 无同名(basename)碰撞，SSOT 成立。")
        return 0

    print("[ssot] ❌ 发现 {} 个双源碰撞（违反 docs/ 唯一权威）：".format(len(collisions)))
    for name in collisions:
        print("  冲突文件: {}".format(name))
        for p in d_map[name]:
            print("    docs      : {}".format(p))
        for p in v_map[name]:
            print("    deliverables: {}".format(p))
        print("  → 处置：将 deliverables/ 副本改名归档至 deliverables/_archive/，docs/ 版保留为权威。")
    return 1


# ---------------------------------------------------------------------------
# 子命令：gate —— 新文档止血闸门（Layer A）
# ---------------------------------------------------------------------------
def cmd_gate(args) -> int:
    candidate = os.path.abspath(args.candidate)
    if not os.path.isfile(candidate):
        print("[gate] ❌ 候选文件不存在: {}".format(candidate))
        return 1
    if "_archive" in candidate.split(os.sep):
        print("[gate] OK：归档区(_archive/)文件豁免检查。")
        return 0

    corpus_files = list(_iter_md(args.corpus)) if os.path.isdir(args.corpus) else []
    if not corpus_files:
        print("[gate] OK：语料为空，放行。")
        return 0

    cand_text = _read(candidate)
    best = None
    best_sim = 0.0
    for cf in corpus_files:
        sim = _similarity(cand_text, _read(cf))
        if sim > best_sim:
            best_sim = sim
            best = cf

    if best_sim >= args.threshold:
        rel = os.path.relpath(best, _repo_root())
        cand_rel = os.path.relpath(candidate, _repo_root())
        print("[gate] ❌ 阻断：{} 与既有文档 {} 近似度 {:.2f} ≥ {:.2f}".format(
            cand_rel, rel, best_sim, args.threshold))
        print("  → 应更新既有文档 {}，而非新建。".format(rel))
        return 1

    print("[gate] OK：最高近似度 {:.2f} < {:.2f}，放行。".format(best_sim, args.threshold))
    return 0


# ---------------------------------------------------------------------------
# 子命令：write —— skill 写盘闸门（Layer A 上游注入点）
# ---------------------------------------------------------------------------
def cmd_write(args) -> int:
    """skill 发射边界的单一写盘闸门：先 gate 草稿，通过才落盘；阻断则不落盘。

    用法（skill 内替换裸 Write 工具）：
      python3 scripts/doc_dedup_guard.py write \
        --draft /tmp/draft.md --out docs/superpowers/specs/xxx.md --corpus docs
    阻断时退出码 1 且不落盘，并打印应更新的既有文件；skill 据此改「更新既有」而非「新建」。
    """
    draft = os.path.abspath(args.draft)
    out = os.path.abspath(args.out)
    if not os.path.isfile(draft):
        print("[write] ❌ 草稿不存在: {}".format(draft))
        return 1
    if "_archive" in out.split(os.sep):
        print("[write] OK：归档区(_archive/)豁免，直接落盘。")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copyfile(draft, out)
        return 0

    corpus_files = list(_iter_md(args.corpus)) if os.path.isdir(args.corpus) else []
    cand_text = _read(draft)
    best, best_sim = None, 0.0
    for cf in corpus_files:
        sim = _similarity(cand_text, _read(cf))
        if sim > best_sim:
            best_sim, best = sim, cf

    if best is not None and best_sim >= args.threshold:
        rel = os.path.relpath(best, _repo_root())
        print("[write] ❌ 阻断：草稿与既有文档 {} 近似度 {:.2f} ≥ {:.2f}".format(
            rel, best_sim, args.threshold))
        print("  → 应更新既有文档 {}，而非新建 {}。".format(rel, os.path.relpath(out, _repo_root())))
        return 1

    os.makedirs(os.path.dirname(out), exist_ok=True)
    text = _read(draft)
    text2 = _ensure_meta(text)
    if text2 != text:
        print("[write] 注入头部日期（创建/更新），满足 2026-10-30 头部日期契约。")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text2)
    print("[write] OK：近似度 {:.2f} < {:.2f}，已落盘 {}".format(
        best_sim, args.threshold, os.path.relpath(out, _repo_root())))
    return 0


# ---------------------------------------------------------------------------
# 子命令：scan —— 存量清算（Layer B）
# ---------------------------------------------------------------------------
def cmd_scan(args) -> int:
    roots = [r for r in (args.docs, args.deliverables) if os.path.isdir(r)]
    files = []
    for r in roots:
        for p in _iter_md(r):
            files.append(p)
    files = sorted(set(files))
    n = len(files)
    print("[scan] 扫描 {} 篇文档（docs={} deliverables={}）...".format(
        n, os.path.isdir(args.docs), os.path.isdir(args.deliverables)))

    # 两两比对，记录超阈值对
    pairs: list[tuple[str, str, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            sim = _similarity(_read(files[i]), _read(files[j]))
            if sim >= args.threshold:
                pairs.append((files[i], files[j], sim))

    # 并查集聚类
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    idx = {p: k for k, p in enumerate(files)}
    for a, b, _ in pairs:
        union(idx[a], idx[b])

    clusters: dict[int, list[int]] = {}
    for k in range(n):
        clusters.setdefault(find(k), []).append(k)

    # 生成报告
    md_lines = ["# 文档冗余清算报告（Layer B）", ""]
    md_lines.append("- 扫描文档数: {}".format(n))
    md_lines.append("- 近似重复对(≥{:.2f}): {}".format(args.threshold, len(pairs)))
    md_lines.append("- 冗余聚类数: {}".format(len([c for c in clusters.values() if len(c) > 1])))
    md_lines.append("")

    cluster_blocks = []
    for members in clusters.values():
        if len(members) <= 1:
            continue
        members_sorted = sorted(members, key=lambda k: -os.path.getsize(files[k]))
        block = {
            "members": [os.path.relpath(files[k], _repo_root()) for k in members_sorted],
            "size": len(members_sorted),
            "max_size_bytes": os.path.getsize(files[members_sorted[0]]),
        }
        cluster_blocks.append(block)

    # 按成员数降序
    cluster_blocks.sort(key=lambda b: -b["size"])
    for i, b in enumerate(cluster_blocks, 1):
        md_lines.append("## 聚类 {}（{} 篇）".format(i, b["size"]))
        md_lines.append("")
        for m in b["members"]:
            md_lines.append("- {}".format(m))
        md_lines.append("")
        md_lines.append("建议：以篇幅最大/最新的一篇为权威，其余合并或归档至 deliverables/_archive/。")
        md_lines.append("")

    report_md = "\n".join(md_lines)
    if args.md:
        os.makedirs(os.path.dirname(args.md) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(report_md)
        print("[scan] 报告已写: {}".format(os.path.relpath(args.md, _repo_root())))

    out = {
        "threshold": args.threshold,
        "scanned": n,
        "duplicate_pairs": [
            {"a": os.path.relpath(files[i], _repo_root()),
             "b": os.path.relpath(files[j], _repo_root()),
             "similarity": round(s, 4)}
            for a, b, s in pairs
        ],
        "clusters": cluster_blocks,
    }
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print("[scan] JSON 已写: {}".format(os.path.relpath(args.json, _repo_root())))

    print("[scan] 完成：{} 个冗余聚类，详见报告。".format(len(cluster_blocks)))
    return 0


# ---------------------------------------------------------------------------
# jscpd 后端（markdown 块级克隆）
# ---------------------------------------------------------------------------
DEFAULT_JSCPD_MIN_TOKENS = 15
DEFAULT_JSCPD_MIN_LINES = 3
# scripts/jscpd/ 下 npm install 固化的 jscpd@4.2.5 二进制（相对本文件）
_JSCPD_PKG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jscpd")


def _resolve_jscpd_bin() -> "str | None":
    """解析 jscpd 二进制，优先级：环境变量 JSCPD_BIN > 本地固化 > PATH。

    不硬编码用户绝对路径：本地固化路径由本文件位置推导，部署时无需改动。
    """
    env = os.environ.get("JSCPD_BIN")
    if env and os.path.isfile(env):
        return env
    local = os.path.join(_JSCPD_PKG_DIR, "node_modules", ".bin", "jscpd")
    if os.path.isfile(local):
        return local
    which = shutil.which("jscpd")
    if which:
        return which
    return None


def _parse_jscpd_report(json_path: str):
    """解析 jscpd JSON 报告，返回 (cross_clones, intra_count)。

    cross_clones: 跨文件克隆列表，每项 {a, b, lines, tokens, snippet}
      a/b 为相对仓库根的文件路径（取自 firstFile.name / secondFile.name）。
    intra_count: 同文件内自克隆数（写作风格噪声，非合并对象，单列统计）。
    注：jscpd v4.2.5 JSON 中文件路径在 firstFile/secondFile.name（dict），
        fragment 字段是重复内容串而非路径；且其 statistics.total.sources
        统计会膨胀（实测 93 > 实际 .md 总数），故报告以真实涉及文件数为准。
    """
    with open(json_path, encoding="utf-8", errors="ignore") as fh:
        data = json.load(fh)
    cross = []
    intra = 0
    for dup in data.get("duplicates", []):
        ff = dup.get("firstFile")
        sf = dup.get("secondFile")
        if not isinstance(ff, dict) or not isinstance(sf, dict):
            continue
        a = ff.get("name")
        b = sf.get("name")
        if not a or not b:
            continue
        if a == b:
            intra += 1
            continue
        cross.append({
            "a": a,
            "b": b,
            "lines": dup.get("lines", 0),
            "tokens": dup.get("tokens", 0),
            "snippet": (dup.get("fragment") or "")[:200],
        })
    return cross, intra


def cmd_jscan(args) -> int:
    """jscan 子命令：jscpd markdown 块级克隆检测（更细于 scan 的整篇相似度）。

    设计要点：
      - 调用 scripts/jscpd/ 固化的 jscpd@4.2.5（markdown 内建可用；v5 二进制不可用）。
      - --no-gitignore 让 deliverables/（被 .gitignore 排除）也参与扫描。
      - 仅保留跨文件克隆；同文件内自克隆视为写作风格噪声，单列统计不进聚类。
      - 二进制缺失时明确报错并给出安装命令，退出码 2（不静默降级为 difflib）。
    """
    bin_path = _resolve_jscpd_bin()
    if not bin_path:
        print("[jscan] ❌ 未找到 jscpd 二进制（需 v4.2.5，markdown 可用）。")
        print("  → 请执行：cd {} && npm install".format(_JSCPD_PKG_DIR))
        print("  （或设置环境变量 JSCPD_BIN 指向 jscpd@4.2.5 二进制）")
        return 2

    roots = [r for r in (args.docs, args.deliverables) if os.path.isdir(r)]
    if not roots:
        print("[jscan] ❌ docs/deliverables 均不存在。")
        return 2

    root = _repo_root()
    ignore = "**/_archive/**,**/_dedup_*,**/node_modules/**"
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            bin_path,
            "-f", "markdown",
            "-k", str(args.min_tokens),
            "-l", str(args.min_lines),
            "-t", "100",            # 关阈值门控，避免误 exit；我们只读报告
            "--no-gitignore",       # deliverables/ 被 .gitignore 排除，需显式纳入
            "-i", ignore,
            "-r", "json",
            "-o", tmp,
        ] + roots
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        report = os.path.join(tmp, "jscpd-report.json")
        if not os.path.isfile(report):
            print("[jscan] ❌ jscpd 未产出报告，stderr：")
            print(proc.stderr.strip()[-800:])
            return 2

        cross, intra = _parse_jscpd_report(report)

    # 跨文件克隆聚类（union-find over 文件路径）
    files = sorted({c["a"] for c in cross} | {c["b"] for c in cross})
    fidx = {f: i for i, f in enumerate(files)}
    parent = list(range(len(files)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for c in cross:
        union(fidx[c["a"]], fidx[c["b"]])

    groups: dict[int, list[int]] = {}
    for i in range(len(files)):
        groups.setdefault(find(i), []).append(i)

    cluster_blocks = []
    for members in groups.values():
        if len(members) <= 1:
            continue
        members_sorted = sorted(members, key=lambda k: -os.path.getsize(files[k]))
        # 该聚类内的跨文件克隆对
        pair_detail = [
            {"a": c["a"], "b": c["b"], "lines": c["lines"], "tokens": c["tokens"]}
            for c in cross
            if fidx[c["a"]] in members and fidx[c["b"]] in members
        ]
        cluster_blocks.append({
            "members": [files[k] for k in members_sorted],
            "size": len(members_sorted),
            "clone_pairs": pair_detail,
        })
    cluster_blocks.sort(key=lambda b: (-b["size"], -len(b["clone_pairs"])))

    # 报告
    md_lines = ["# 文档块级重复清算报告（jscan / jscpd markdown）", ""]
    md_lines.append("- 引擎: jscpd@4.2.5（markdown 块级克隆）")
    md_lines.append("- 阈值: min_tokens={} min_lines={}".format(args.min_tokens, args.min_lines))
    md_lines.append("- 跨文件克隆块: {}".format(len(cross)))
    md_lines.append("- 同文件自克隆(写作风格,非合并对象): {}".format(intra))
    md_lines.append("- 跨文件冗余聚类数: {}".format(len(cluster_blocks)))
    md_lines.append("")
    md_lines.append("> 与 `scan`（difflib 整篇相似度）互补：jscan 挖跨文档的重复段落（块级），"
                    "scan 抓近重复全篇。两者共同标记的聚类应优先合并。")
    md_lines.append("")
    for i, b in enumerate(cluster_blocks, 1):
        md_lines.append("## 聚类 {}（{} 篇, {} 处跨文件块重复）".format(i, b["size"], len(b["clone_pairs"])))
        md_lines.append("")
        for m in b["members"]:
            md_lines.append("- {}".format(m))
        md_lines.append("")
        md_lines.append("跨文件块重复明细：")
        for p in b["clone_pairs"]:
            md_lines.append("  - `{}` ↔ `{}`（{} 行 / {} tokens）".format(
                p["a"], p["b"], p["lines"], p["tokens"]))
        md_lines.append("")
        md_lines.append("建议：以篇幅最大/最新的一篇为权威，其余合并或归档至 deliverables/_archive/。")
        md_lines.append("")

    report_md = "\n".join(md_lines)
    if args.md:
        os.makedirs(os.path.dirname(args.md) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(report_md)
        print("[jscan] 报告已写: {}".format(os.path.relpath(args.md, root)))

    out = {
        "engine": "jscpd@4.2.5",
        "min_tokens": args.min_tokens,
        "min_lines": args.min_lines,
        "cross_clones": len(cross),
        "intra_clones": intra,
        "clusters": cluster_blocks,
    }
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print("[jscan] JSON 已写: {}".format(os.path.relpath(args.json, root)))

    print("[jscan] 完成：{} 个跨文件聚类 / {} 处跨文件块重复（另有 {} 处同文件自克隆）。".format(
        len(cluster_blocks), len(cross), intra))
    return 0


# ---------------------------------------------------------------------------
# compare —— 双视角比对（difflib 整篇 vs jscpd 块级）
# ---------------------------------------------------------------------------
def cmd_compare(args) -> int:
    """compare 子命令：运行 scan(jscpd 块级) + scan(difflib 整篇)，输出双视角对照。"""
    root = _repo_root()
    scan_md = os.path.join(root, "docs", "_dedup_report.md")
    scan_json = os.path.join(root, "docs", "_dedup_report.json")
    jscan_md = os.path.join(root, "docs", "_dedup_report_jscan.md")
    jscan_json = os.path.join(root, "docs", "_dedup_report_jscan.json")
    compare_md = os.path.join(root, "docs", "_dedup_compare.md")

    # 1) scan（difflib 整篇）
    rc1 = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "scan",
         "--md", scan_md, "--json", scan_json], cwd=root).returncode
    # 2) jscan（jscpd 块级）
    rc2 = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "jscan",
         "--md", jscan_md, "--json", jscan_json], cwd=root).returncode

    scan_data = json.load(open(scan_json, encoding="utf-8")) if os.path.isfile(scan_json) else {}
    jscan_data = json.load(open(jscan_json, encoding="utf-8")) if os.path.isfile(jscan_json) else {}

    # 提取两视角涉及的「文件集」用于对照
    scan_files = set()
    for cl in scan_data.get("clusters", []):
        scan_files.update(cl.get("members", []))
    jscan_files = set()
    for cl in jscan_data.get("clusters", []):
        jscan_files.update(cl.get("members", []))

    lines = ["# 文档去重双视角对照报告（difflib 整篇 vs jscpd 块级）", ""]
    lines.append("> 生成于 compare 子命令。两视角互补：difflib 抓近重复全篇，jscpd 挖跨文档重复段落。")
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append("| 视角 | 引擎 | 聚类数 | 涉及文件数 | 备注 |")
    lines.append("|------|------|--------|------------|------|")
    lines.append("| A 整篇相似度 | difflib.SequenceMatcher | {} | {} | 阈值 {}，整篇两两比对 |".format(
        len(scan_data.get("clusters", [])), len(scan_files), scan_data.get("threshold")))
    lines.append("| B 块级克隆 | jscpd@4.2.5 markdown | {} | {} | 跨文件块重复 {} 处 |".format(
        len(jscan_data.get("clusters", [])), len(jscan_files), jscan_data.get("cross_clones")))
    lines.append("")
    lines.append("## A 视角：difflib 整篇相似度聚类")
    lines.append("")
    if scan_data.get("clusters"):
        for i, cl in enumerate(scan_data["clusters"], 1):
            lines.append("### A{}（{} 篇）".format(i, cl.get("size")))
            for m in cl.get("members", []):
                lines.append("- {}".format(m))
            lines.append("")
    else:
        lines.append("（无聚类）")
        lines.append("")
    lines.append("## B 视角：jscpd 跨文件块级聚类")
    lines.append("")
    if jscan_data.get("clusters"):
        for i, cl in enumerate(jscan_data["clusters"], 1):
            lines.append("### B{}（{} 篇, {} 处跨文件块重复）".format(
                i, cl.get("size"), len(cl.get("clone_pairs", []))))
            for m in cl.get("members", []):
                lines.append("- {}".format(m))
            lines.append("")
    else:
        lines.append("（无跨文件聚类）")
        lines.append("")
    lines.append("## 对照结论")
    lines.append("")
    only_b = jscan_files - scan_files
    if only_b:
        lines.append("- jscan 额外挖出、difflib 未标记的跨文件块重复文件（块级比整篇更敏感）：")
        for f in sorted(only_b):
            lines.append("  - {}".format(f))
        lines.append("")
    common = scan_files & jscan_files
    if common:
        lines.append("- 两视角共同标记的聚类（应优先合并清算）：")
        for f in sorted(common):
            lines.append("  - {}".format(f))
        lines.append("")
    lines.append("- 治理建议：两视角任一标红的聚类均须合并/归档；jscan 的块级明细可定位到具体重复段落，"
                  "便于精准改写而非整篇丢弃。")
    lines.append("")

    with open(compare_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("[compare] 双视角对照已写: {}".format(os.path.relpath(compare_md, root)))
    print("[compare] scan 退出={} jscan 退出={}".format(rc1, rc2))
    return 0


# ---------------------------------------------------------------------------
# init — 跨项目自动部署（探测 + 修复 + 幂等）
# ---------------------------------------------------------------------------
# 钩子模板：守卫脚本随仓库自包含于 .githooks/dedup/，解耦任何 IDE / agent 工具。
# 注意：raw string 内 $ROOT / $(...) 原样保留，shell 提交时正常展开（勿加反斜杠）。
_HOOK_TEMPLATE = r"""#!/bin/sh
# .githooks/pre-commit — 文档治理守卫（per-repo 自包含，由 doc_dedup_guard.py init 部署）
#
# 机制：提交前拦截「文档过度生产 / 内容重复」三类违规：
#   1) ssot  : docs/ 与 deliverables/ 同名碰撞 → 硬阻断（违反 SSOT 铁律）
#   2) gate  : 新增/修改的 .md 与异树既有文档近似度 ≥ 0.90 → 阻断（应更新既有而非新建）
#
# ⚠️ scan 已于 2026-10-08 移出提交关键路径：O(n²) 整篇字符级两两比对，
#    173 篇 → 14878 对，每次提交多耗数分钟，且结果无人当场消费（原挂 || true）。
#    需要全量清算时按需跑：python3 scripts/doc_dedup_guard.py scan
#
# 本脚本随仓库自包含（.githooks/dedup/），不依赖任何外部工具目录。
# 紧急跳过： git commit --no-verify
set -e

ROOT=$(git rev-parse --show-toplevel)
GUARD="$ROOT/.githooks/dedup/doc_dedup_guard.py"
PY="${PYTHON:-python3}"

# 0) 既有 gitignore 严格校验（脚本存在时执行；warn-only 不阻断）。
#    注意：必须 warn-only 而非 exit 1——仓库存在「已跟踪却命中 .gitignore」的历史文件，
#    若阻断会导致任何提交都无法完成。
if [ -f "$ROOT/scripts/validate_gitignore_compliance.py" ]; then
  if ! "$PY" "$ROOT/scripts/validate_gitignore_compliance.py"; then
    echo "⚠️ 命中 .gitignore 严格规则（见 scripts/validate_gitignore_compliance.py）；建议清理后再提交（仅警告，不阻断）。"
  fi
fi

if [ ! -f "$GUARD" ]; then
  echo "⚠️ 文档治理守卫未部署：请运行 \`python3 doc_dedup_guard.py init\`（或重新 clone 含 .githooks 的仓库）。"
  exit 1
fi

# 1) 双源碰撞硬阻断
if ! "$PY" "$GUARD" ssot --docs "$ROOT/docs" --deliverables "$ROOT/deliverables" --staged; then
  echo "❌ 双源碰撞：deliverables/ 与 docs/ 存在同名文档，违反 SSOT（docs/ 唯一权威）。"
  echo "   处置：将 deliverables/ 副本改名归档至 deliverables/_archive/，保留 docs/ 版。"
  exit 1
fi

# 2) 文件命名契约（2026-10-08 用户裁定）：docs/ 下带日期前缀的文档必须是
#    「YYYY-MM-DD-中文名.md」——日期后以中文开头，禁空格与 Windows 非法字符
#    \ / : * ? " < > |，文件名 <= 60 字符。dated 目录（engineering-assurance /
#    superpowers/plans|specs / todo）内不许出现无日期前缀的文档。
if [ -f "$ROOT/scripts/docs_index.py" ]; then
  "$PY" "$ROOT/scripts/docs_index.py" names --staged || exit 1
fi

# 2.5) 头部日期契约（2026-10-30 用户裁定）：docs/ 下文档顶部（前 20 行）须含
#      「创建日期」与「更新日期」。--staged 覆盖新增+修改（改文档也要维护头部日期）。
if [ -f "$ROOT/scripts/docs_index.py" ]; then
  "$PY" "$ROOT/scripts/docs_index.py" meta --staged || exit 1
fi

# 2.6) 代码变更文档同步提示（report-only）：历史共现只能提示风险，
#      内容正确性由实施者同一变更内收口保证。
if [ -f "$ROOT/scripts/check_doc_impact.py" ]; then
  if ! "$PY" "$ROOT/scripts/check_doc_impact.py" --mode report; then
    echo "⚠️ 文档同步影响检查未完成；请检查上文提示并更新受影响文档。"
  fi
fi

# 2.7) 锚点与索引硬门禁：契约类锚点错误或索引过期必须修复后提交。
if [ -f "$ROOT/scripts/check_doc_anchors.py" ]; then
  "$PY" "$ROOT/scripts/check_doc_anchors.py" --staged || exit 1
fi
if [ -f "$ROOT/scripts/docs_index.py" ]; then
  "$PY" "$ROOT/scripts/docs_index.py" check --staged || exit 1
fi

# 3) 新增文档近似重复检查：使用 NUL 分隔路径和暂存内容。
if ! "$PY" - "$ROOT" "$GUARD" <<'PY_DOC_GATE'
import os
import io
import subprocess
import sys
import tempfile

root, guard = sys.argv[1:]
try:
    paths = subprocess.run(
        ['git', '-C', root, 'diff', '--cached', '--name-only', '-z', '--diff-filter=A'],
        check=True, stdout=subprocess.PIPE,
    ).stdout.split(b'\0')
    paths = [os.fsdecode(raw) for raw in paths if raw]
    paths = [rel for rel in paths if rel.endswith('.md') and '_archive/' not in rel]
    with tempfile.TemporaryDirectory(prefix='staged-doc-gate-') as temp:
        candidate = os.path.join(temp, 'candidate.md')
        corpus_root = os.path.join(temp, 'corpus')
        if paths:
            tracked = subprocess.run(
                ['git', '-C', root, 'ls-files', '-z', '--', 'docs', 'deliverables'],
                check=True, stdout=subprocess.PIPE,
            ).stdout.split(b'\0')
            corpus_paths = [os.fsdecode(raw) for raw in tracked if raw]
            corpus_paths = [rel for rel in corpus_paths if rel.endswith('.md')
                            and '_archive' not in rel.split('/')
                            and not os.path.basename(rel).startswith('_dedup_report')]
            blobs = subprocess.run(
                ['git', '-C', root, 'cat-file', '--batch', '-z'], check=True,
                input=b''.join(b':' + os.fsencode(rel) + b'\0' for rel in corpus_paths),
                stdout=subprocess.PIPE,
            ).stdout
            stream = io.BytesIO(blobs)
            for rel in corpus_paths:
                header = stream.readline().rstrip(b'\n').split(b' ')
                if len(header) != 3 or header[1] != b'blob':
                    raise ValueError('cannot read staged corpus: ' + rel)
                size = int(header[2])
                data = stream.read(size)
                if len(data) != size or stream.read(1) != b'\n':
                    raise ValueError('truncated staged corpus: ' + rel)
                target = os.path.join(corpus_root, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, 'wb') as output:
                    output.write(data)
        for rel in paths:
            content = subprocess.run(
                ['git', '-C', root, 'show', ':' + rel],
                check=True, stdout=subprocess.PIPE,
            ).stdout
            with open(candidate, 'wb') as output:
                output.write(content)
            corpus = os.path.join(corpus_root, 'docs' if rel.startswith('deliverables/') else 'deliverables')
            print('[gate] 暂存文档: ' + os.path.join(root, rel), flush=True)
            result = subprocess.run(
                [sys.executable, guard, 'gate', candidate, '--corpus', corpus, '--threshold', '0.90'],
                capture_output=True, text=True,
            )
            output = result.stdout.replace(os.path.relpath(candidate, root), rel)
            output = output.replace(os.path.relpath(corpus_root, root) + os.sep, '')
            print(output, end='', flush=True)
            print(result.stderr, end='', file=sys.stderr, flush=True)
            if result.returncode:
                sys.exit(result.returncode)
except (OSError, ValueError, subprocess.CalledProcessError) as error:
    print('[gate] 无法读取或检查暂存文档: ' + str(error), file=sys.stderr)
    sys.exit(2)
PY_DOC_GATE
then
  echo "❌ 暂存文档去重检查未通过，请检查上述原因。"
  exit 1
fi

exit 0
"""


def _need_copy_from_text(text: str, dst: str) -> bool:
    """dst 不存在或内容（归一化）与 text 不一致则 True。"""
    if not os.path.isfile(dst):
        return True
    try:
        with open(dst, encoding="utf-8") as b:
            return _normalize(text) != _normalize(b.read())
    except Exception:
        return True


def cmd_init(args) -> int:
    """跨项目自动部署文档治理机制（探测 + 修复 + 幂等）。

    把守卫脚本随仓库自包含（.githooks/dedup/），解耦任何 IDE / agent；
    部署 pre-commit 钩子 + 设 core.hooksPath，使任意 git commit 都触发。
    """
    root = _repo_root()
    dedup_dir = os.path.join(root, ".githooks", "dedup")
    primary = os.path.join(dedup_dir, "doc_dedup_guard.py")
    hook = os.path.join(root, ".githooks", "pre-commit")
    scripts_dir = os.path.join(root, "scripts")
    scripts_copy = os.path.join(scripts_dir, "doc_dedup_guard.py")
    jscpd_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jscpd", "package.json")
    jscpd_dst = os.path.join(dedup_dir, "jscpd", "package.json")

    steps = []
    os.makedirs(dedup_dir, exist_ok=True)

    # 主副本（钩子引用，per-repo 自包含）
    if _need_copy_from_text(_read_file(os.path.abspath(__file__)), primary):
        shutil.copyfile(os.path.abspath(__file__), primary)
        steps.append("部署主副本 → .githooks/dedup/doc_dedup_guard.py")

    # scripts/ 副本（供 skill 写盘闸门 + 手动命令；仅当项目已有 scripts/）
    if os.path.isdir(scripts_dir) and _need_copy_from_text(_read_file(os.path.abspath(__file__)), scripts_copy):
        shutil.copyfile(os.path.abspath(__file__), scripts_copy)
        steps.append("部署 scripts/doc_dedup_guard.py（skill 闸门 / 手动命令兼容）")

    # jscpd 包定义（块级检测；node_modules 需 cd 该目录 npm install）
    if os.path.isfile(jscpd_src):
        os.makedirs(os.path.dirname(jscpd_dst), exist_ok=True)
        if _need_copy_from_text(_read_file(jscpd_src), jscpd_dst):
            shutil.copyfile(jscpd_src, jscpd_dst)
            steps.append("复制 jscpd/package.json → .githooks/dedup/jscpd/（首次用 jscan 前 cd 该目录 npm install）")

    # pre-commit 钩子
    if _need_copy_from_text(_HOOK_TEMPLATE, hook):
        with open(hook, "w", encoding="utf-8") as fh:
            fh.write(_HOOK_TEMPLATE)
        os.chmod(hook, 0o755)
        steps.append("部署 .githooks/pre-commit 钩子")

    # core.hooksPath 配置
    cur = subprocess.run(["git", "config", "core.hooksPath"],
                         cwd=root, capture_output=True, text=True).stdout.strip()
    if cur != ".githooks":
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"],
                       cwd=root, check=True)
        steps.append("git config core.hooksPath .githooks")

    if steps:
        print("[init] 已部署/修复文档治理机制：")
        for s in steps:
            print("  + " + s)
        print("[init] 完成。任意 git commit 将自动触发守卫；jscan 块级检测按需 npm install。")
    else:
        print("[init] 已是最新，无需更改。")
    return 0


def _read_file(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def cmd_status(args) -> int:
    """自检：一眼确认文档治理机制是否已在本仓库生效。

    对齐 init 部署的全部目标（主副本 / 钩子 / hooksPath / jscpd），
    打印 ✓/✗ 清单；未完全生效时给出修复命令。返回 0=生效，1=未完全生效。
    """
    root = _repo_root()
    dedup_dir = os.path.join(root, ".githooks", "dedup")
    primary = os.path.join(dedup_dir, "doc_dedup_guard.py")
    hook = os.path.join(root, ".githooks", "pre-commit")
    jscpd_dst = os.path.join(dedup_dir, "jscpd", "package.json")

    print("[status] 文档治理机制自检：")
    ok = True

    # 1) git 仓库
    print("  ✓ 已在 git 仓库（root={}）".format(root))

    # 2) 钩子存在且引用自包含路径
    hook_ok = os.path.isfile(hook)
    ref_ok = False
    if hook_ok:
        ref_ok = ".githooks/dedup/doc_dedup_guard.py" in _read_file(hook)
    if hook_ok and ref_ok:
        print("  ✓ .githooks/pre-commit 存在且引用自包含副本")
    elif not hook_ok:
        print("  ✗ .githooks/pre-commit 缺失")
        ok = False
    else:
        print("  ✗ pre-commit 未引用 .githooks/dedup/ 自包含副本")
        ok = False

    # 2b) 慢扫描回归检测：全量 scan 不应回到提交路径（2026-10-08 移出，O(n²) 实测数分钟）
    if hook_ok and '"$GUARD" scan' in _read_file(hook):
        print("  ⚠️ pre-commit 又在执行全量 scan（提交会慢数分钟）；非有意恢复时请移出，详见钩子顶部说明")
    elif hook_ok:
        print("  ✓ pre-commit 未执行全量 scan（仅 ssot + gate 两道硬门禁）")

    # 3) core.hooksPath
    cur = subprocess.run(["git", "config", "core.hooksPath"],
                         cwd=root, capture_output=True, text=True).stdout.strip()
    if cur == ".githooks":
        print("  ✓ core.hooksPath = .githooks")
    else:
        print("  ✗ core.hooksPath 未设置（当前={}）；守卫不会自动触发".format(cur or "(空)"))
        ok = False

    # 4) 主副本存在且与源一致
    src = os.path.abspath(__file__)
    if os.path.isfile(primary):
        if not _need_copy_from_text(_read_file(src), primary):
            print("  ✓ 主副本 .githooks/dedup/doc_dedup_guard.py 与源一致")
        else:
            print("  ✗ 主副本与源不一致（运行 `doc_dedup_guard.py init` 修复）")
            ok = False
    else:
        print("  ✗ 主副本缺失（运行 `doc_dedup_guard.py init` 部署）")
        ok = False

    # 5) jscpd 包定义（仅影响 jscan，不阻断核心守卫）
    if os.path.isfile(jscpd_dst):
        print("  - jscpd 包定义存在（块级检测按需 cd .githooks/dedup/jscpd && npm install）")
    else:
        print("  - jscpd 包定义缺失（不影响 ssot/gate；用 jscan 前先 init）")

    print("")
    if ok:
        print("  [结论] 机制已生效：任意 git commit 将自动触发文档治理守卫。")
    else:
        print("  [结论] 机制未完全生效：运行 `doc_dedup_guard.py init` 自动修复。")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    root = _repo_root()
    p = argparse.ArgumentParser(
        description="文档去重治理工具（SSOT 守卫 / 止血闸门 / 存量清算）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ssot", help="双源碰撞守卫（docs/ vs deliverables/ 同名）")
    s.add_argument("--docs", default=os.path.join(root, "docs"))
    s.add_argument("--deliverables", default=os.path.join(root, "deliverables"))
    s.add_argument("--staged", action="store_true", help="检查 Git 暂存快照")
    s.set_defaults(func=cmd_ssot)

    g = sub.add_parser("gate", help="新文档止血闸门：近似既有文档则阻断")
    g.add_argument("candidate", help="候选新文档路径")
    g.add_argument("--corpus", required=True, help="既有语料目录（如 docs/ 或 deliverables/）")
    g.add_argument("--threshold", type=float, default=DEFAULT_GATE_THRESHOLD)
    g.set_defaults(func=cmd_gate)

    w = sub.add_parser("write", help="skill 写盘闸门：先 gate 草稿，通过才落盘（Layer A 上游注入）")
    w.add_argument("--draft", required=True, help="草稿文件路径（skill 先写出草稿）")
    w.add_argument("--out", required=True, help="最终落盘路径")
    w.add_argument("--corpus", required=True, help="既有语料目录（如 docs/ 或 deliverables/）")
    w.add_argument("--threshold", type=float, default=DEFAULT_GATE_THRESHOLD)
    w.set_defaults(func=cmd_write)

    sc = sub.add_parser("scan", help="存量清算：全量两两近似度聚类")
    sc.add_argument("--docs", default=os.path.join(root, "docs"))
    sc.add_argument("--deliverables", default=os.path.join(root, "deliverables"))
    sc.add_argument("--threshold", type=float, default=DEFAULT_SCAN_THRESHOLD)
    sc.add_argument("--md", default=os.path.join(root, "docs", "_dedup_report.md"))
    sc.add_argument("--json", default=os.path.join(root, "docs", "_dedup_report.json"))
    sc.set_defaults(func=cmd_scan)

    js = sub.add_parser("jscan", help="块级克隆清算：jscpd markdown 跨文件块重复（比 scan 更细）")
    js.add_argument("--docs", default=os.path.join(root, "docs"))
    js.add_argument("--deliverables", default=os.path.join(root, "deliverables"))
    js.add_argument("--min-tokens", type=int, default=DEFAULT_JSCPD_MIN_TOKENS)
    js.add_argument("--min-lines", type=int, default=DEFAULT_JSCPD_MIN_LINES)
    js.add_argument("--md", default=os.path.join(root, "docs", "_dedup_report_jscan.md"))
    js.add_argument("--json", default=os.path.join(root, "docs", "_dedup_report_jscan.json"))
    js.set_defaults(func=cmd_jscan)

    cp = sub.add_parser("compare", help="双视角对照：scan(difflib 整篇) vs jscan(jscpd 块级)")
    cp.add_argument("--docs", default=os.path.join(root, "docs"))
    cp.add_argument("--deliverables", default=os.path.join(root, "deliverables"))
    cp.set_defaults(func=cmd_compare)

    ini = sub.add_parser("init", help="跨项目自动部署：探测+修复钩子/hooksPath/脚本（幂等）")
    ini.set_defaults(func=cmd_init)

    st = sub.add_parser("status", help="自检：一眼确认文档治理机制是否已在本仓库生效")
    st.set_defaults(func=cmd_status)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
