#!/usr/bin/env python3
"""validate.py — 多策略量化筛选 skill 自检脚本（仅标准库，零外部依赖）。

校验项：
1. SKILL.md frontmatter 合规（name / description / version / compatibility / metadata）
2. 版本一致性（config.VERSION 与 SKILL.md frontmatter version 一致）
3. 引用完整性（SKILL.md 提及的 scripts 路径全部存在）
4. 策略注册表一致性（STRATEGY_REGISTRY 覆盖 S01-S17 共 17 种）
5. Python 语法（scripts/ 下全部 .py 通过编译检查）
6. 表面话术检查（无开发日志 / 版本历史痕迹，如"实测/旧实现/修复 2026/旧版本号"）

用法：python scripts/validate.py
退出码：0=全部通过；1=存在未通过项。
"""
import os
import re
import sys
import py_compile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "SKILL.md")
SCRIPTS = os.path.join(ROOT, "scripts")
FAIL: list[str] = []


def check(ok: bool, label: str) -> None:
    print(("  ✓ " if ok else "  ✗ ") + label)
    if not ok:
        FAIL.append(label)


def _frontmatter() -> dict:
    text = open(SKILL, encoding="utf-8").read()
    m = re.match(r"^---\n([\s\S]*?)\n---", text)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    fields["_raw"] = m.group(1)  # frontmatter 原文（嵌套字段存在性检查用）
    return fields


def main() -> int:
    print("== 1. frontmatter 合规 ==")
    fm = _frontmatter()
    for key in ("name", "description", "version", "compatibility"):
        check(bool(fm.get(key)), f"frontmatter 含 {key} 字段")
    check("metadata:" in fm.get("_raw", ""), "frontmatter 含 metadata 字段（嵌套）")
    check(fm.get("name") == "stock-selecter-pro", "name 为 stock-selecter-pro")

    print("== 2. 版本一致性 ==")
    sys.path.insert(0, SCRIPTS)
    import config  # noqa: E402
    check(config.VERSION == fm.get("version"), f"config.VERSION({config.VERSION}) == frontmatter version({fm.get('version')})")
    check(fm.get("version") == "1.0.3", "版本为 1.0.3")

    print("== 3. 引用完整性（SKILL.md 提及的 scripts 路径）==")
    skill = open(SKILL, encoding="utf-8").read()
    refs = sorted(set(re.findall(r"scripts/[\w/]+\.py", skill)))
    for r in refs:
        check(os.path.exists(os.path.join(ROOT, r)), f"{r} 存在")
    print(f"  引用 {len(refs)} 个 scripts 路径")

    print("== 4. 策略注册表一致性 ==")
    import strategies  # noqa: E402
    registry = strategies.STRATEGY_REGISTRY
    declared = {f"S{i:02d}" for i in range(1, 18)}
    actual = set(registry.keys())
    check(declared == actual, f"注册表覆盖 S01-S17（实际 {len(actual)} 种）")
    missing = declared - actual
    extra = actual - declared
    if missing:
        check(False, f"缺失策略: {sorted(missing)}")
    if extra:
        check(False, f"多余策略: {sorted(extra)}")

    print("== 5. Python 语法 ==")
    py_files = []
    for root, _, files in os.walk(SCRIPTS):
        if "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    err = 0
    for p in py_files:
        try:
            py_compile.compile(p, doraise=True)
        except py_compile.PyCompileError as e:
            check(False, f"{os.path.relpath(p, ROOT)} 语法错误: {e}")
            err += 1
    if err == 0:
        check(True, f"全部 {len(py_files)} 个 .py 编译通过")

    print("== 6. 表面话术检查 ==")
    pattern = re.compile(r"实测|旧实现|旧逻辑|修复 2026|2026-08|v1\.0\.2|国泰海通|5\.31")
    hits = []
    for root, _, files in os.walk(os.path.join(ROOT, "scripts")):
        if "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                if os.path.basename(p) == "validate.py":
                    continue  # 自检脚本自身含检查词，跳过
                for i, line in enumerate(open(p, encoding="utf-8"), 1):
                    if pattern.search(line):
                        hits.append(f"{os.path.relpath(p, ROOT)}:{i}")
    check(not hits, f"表面无开发日志话术（残留 {len(hits)} 处）")
    for h in hits[:5]:
        print(f"    {h}")

    print()
    if FAIL:
        print(f"结果: {len(FAIL)} 项未通过")
        return 1
    print("结果: 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
