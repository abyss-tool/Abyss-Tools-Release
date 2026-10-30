#!/usr/bin/env python3
"""发布仓清单门禁：version.json / patches.json / changelog.json 三份清单的
一致性与 schema 校验（对应开发仓 tools/validate_manifests.py 的同构校验）。"""
import json
import re
import sys
from pathlib import Path

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def load(name: str) -> dict:
    path = Path(name)
    if not path.exists():
        fail(f"缺少 {name}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{name} JSON 解析失败: {e}")
        return {}


version = load("version.json")
patches = load("patches.json")
changelog = load("changelog.json")

# ── version.json ───────────────────────────────────────────────────
vn = version.get("versionName", "")
if not SEMVER.match(vn):
    fail(f"version.json.versionName 非法 SemVer → {vn!r}")
if not isinstance(version.get("versionCode"), int) or version.get("versionCode", 0) < 1:
    fail("version.json.versionCode 应为正整数")
if version.get("tag") != f"v{vn}":
    fail(f"version.json.tag({version.get('tag')}) 与 v{vn} 不一致")
patch = version.get("patch")
if patch is not None:
    if not patch.get("url"):
        fail("version.json.patch.url 缺失")
    if not str(patch.get("fromTag", "")).startswith("v"):
        fail("version.json.patch.fromTag 应为 v 前缀 tag")
    if patch.get("toTag") is not None and patch["toTag"] != f"v{vn}":
        fail("version.json.patch.toTag 应指向本版 tag")
download = version.get("download")
if download is not None and not download.get("url"):
    fail("version.json.download.url 缺失")

# ── patches.json ───────────────────────────────────────────────────
if patches.get("schema") != "abyss-patches-v1":
    fail("patches.json.schema 应为 abyss-patches-v1")
if patches.get("latestTag") != f"v{vn}":
    fail(f"patches.json.latestTag({patches.get('latestTag')}) 与 v{vn} 不一致")
seen = set()
for entry in patches.get("patches", []):
    key = (entry.get("fromTag"), entry.get("toTag"))
    if key in seen:
        fail(f"patches.json 重复补丁段 {key}")
    seen.add(key)
    if not entry.get("url"):
        fail(f"patches.json 补丁 {key} 缺 url")
    if str(entry.get("toTag", "")) != f"v{vn}" and entry.get("toTag") != patches.get("latestTag"):
        # 历史补丁允许，但必须严格递增链（from < to 由人工保证，CI 只做结构校验）
        pass

# ── changelog.json ─────────────────────────────────────────────────
if changelog.get("schema") != "abyss-changelog-v1":
    fail("changelog.json.schema 应为 abyss-changelog-v1")
latest = changelog.get("latest", {})
if latest.get("versionName") != vn:
    fail(f"changelog.json.latest.versionName({latest.get('versionName')}) 与 {vn} 不一致")
if latest.get("tag") != f"v{vn}":
    fail("changelog.json.latest.tag 与本版 tag 不一致")
if not latest.get("title") or not latest.get("notes"):
    fail("changelog.json.latest 缺 title / notes")
history = changelog.get("history", [])
if history and history[0].get("versionName") != vn:
    fail("changelog.json.history[0] 应为本版（发布后归档）")

if errors:
    print(f"[manifests] ✗ {len(errors)} 处校验失败：", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)
print(f"[manifests] ✓ 发布仓清单校验通过（v{vn} · {len(patches.get('patches', []))} 条补丁记录）")
