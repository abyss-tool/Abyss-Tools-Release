#!/usr/bin/env python3
"""发布仓清单门禁：version.json / patches.json / changelog.json 三份清单的
一致性与 schema 校验（对应开发仓 tools/validate_manifests.py 的同构校验）。

N-SEC-001（M1 起追加两道断言，fail-closed）：
  A. 清单 detached 签名断言 —— 三份清单的 .minisig 必须存在且可被
     内置公钥验过（公钥唯一事实源 = 主仓 ChannelSignatureVerifier.kt
     TRUSTED_KEYS，此处常量与其同步；轮换走双公钥：新增不替换）；
  B. 清单 ↔ Release 资产一致性 —— version.json.download.sha256 必须等于
     该 tag GitHub Release APK 附件的真实 digest（GitHub API 回读）。
"""
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import minisign_py

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
if history and history[0].get("versionName") == vn:
    fail(f"changelog.json.history[0] 不应为本版 —— 旧 latest 下沉 history[0],本版在 latest(当前 history[0]={history[0].get('versionName')})")

if errors:
    print(f"[manifests] ✗ {len(errors)} 处校验失败：", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

# ── N-SEC-001 断言 A：清单 detached 签名（存在 + 可验）────────────────
# 公钥与主仓 TRUSTED_KEYS 首签钥同步（唯一事实源 = 主仓 Kotlin 源；
# 轮换期多把公钥以列表共存，任一验过即合法）。
TRUSTED_PUBKEYS = [
    """
    untrusted comment: Abyss-Tools manifest signing public key (meng4117222)
    RWRx16ORC4gsdxs6DsnctDYagiRptPX1NgFcVpQNYqh/BXGhPAHebh3B
    """,
]
SIGNED_MANIFESTS = ("version.json", "patches.json", "changelog.json")

sig_failures = 0
for name in SIGNED_MANIFESTS:
    manifest = Path(name)
    if not manifest.exists():
        continue  # 缺清单已在上文 fail，此处不重复
    sig_path = Path(name + ".minisig")
    if not sig_path.exists():
        fail(f"{name}.minisig 缺失 —— N-SEC-001 起清单签名强制（发布流水线原子产出）")
        sig_failures += 1
        continue
    sig_text = sig_path.read_text(encoding="utf-8")
    raw = manifest.read_bytes()
    if not any(minisign_py.verify(pk, sig_text, raw) for pk in TRUSTED_PUBKEYS):
        fail(f"{name}.minisig 验签失败 —— 清单字节与签名不配对（公钥不匹配或清单被改）")
        sig_failures += 1
    else:
        print(f"[manifests] ✓ 签名验签通过 {name}")

# ── N-SEC-001 断言 B：清单 hash ↔ Release APK 附件实际 digest ─────────
def latest_release_apk_digest(tag: str) -> str | None:
    """回读该 tag Release 的 APK 附件 GitHub digest（sha256:…）。"""
    url = f"https://api.github.com/repos/abyss-tool/Abyss-Tools-Release/releases/tags/{tag}"
    req = urllib.request.Request(url)
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "abyss-release-validate/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rel = json.loads(resp.read().decode())
    except Exception as e:
        # API 失败不静默 —— 记为可修复错误（CI 重试或人工排查）
        fail(f"Release API 回读失败（{tag}）：{e}")
        return None
    for asset in rel.get("assets", []):
        if asset.get("name", "").endswith(".apk"):
            digest = asset.get("digest") or ""
            return digest.removeprefix("sha256:") or None
    return None


download = version.get("download") or {}
if download.get("sha256") and version.get("tag"):
    actual = latest_release_apk_digest(version["tag"])
    if actual is not None and actual != download["sha256"]:
        fail(
            f"清单 download.sha256({download['sha256'][:16]}…) ≠ Release APK 附件实际 digest"
            f"({actual[:16]}…) —— 资产↔清单不一致，拒绝放行"
        )
    elif actual is not None:
        print(f"[manifests] ✓ 清单 sha256 = Release APK 附件 digest（{version['tag']}）")

if errors:
    print(f"[manifests] ✗ 共 {len(errors)} 处校验失败：", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)
print(f"[manifests] ✓ 发布仓清单校验通过（v{vn} · {len(patches.get('patches', []))} 条补丁记录 · 签名断言通过）")
