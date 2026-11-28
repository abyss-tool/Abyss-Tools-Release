"""validate_manifests.py（发布仓清单门禁）常驻单测。

脚本为模块级执行（无 main 守卫），统一走子进程 + 临时夹具目录。
签名阶段钉的是 TRUSTED_PUBKEYS 常量（私钥 = CI secret，测试不可持有），
故绿色签名路径不在本套件内；此处覆盖：
  - 结构校验逐分支 fail-closed（N-SEC-001 断言 A 之前的三清单一致性）；
  - 签名强制与错签拒收（生成密钥证明 fail-closed，不依赖 secret）。
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
SCRIPT = TOOLS / "validate_manifests.py"


def make_fixtures() -> dict:
    return {
        "version.json": {
            "versionName": "1.2.3",
            "versionCode": 42,
            "tag": "v1.2.3",
        },
        "patches.json": {
            "schema": "abyss-patches-v1",
            "latestTag": "v1.2.3",
            "patches": [{
                "fromTag": "v1.1.0",
                "toTag": "v1.2.3",
                "url": "https://example.com/patch-v1.2.3.zip",
            }],
        },
        "changelog.json": {
            "schema": "abyss-changelog-v1",
            "latest": {"versionName": "1.2.3", "tag": "v1.2.3",
                       "title": "v1.2.3", "notes": ["- a", "- b"]},
            "history": [{"versionName": "1.1.0", "tag": "v1.1.0",
                         "title": "old", "notes": ["- x"]}],
        },
    }


def write_fixtures(tmp_path: Path, mutations: dict | None = None,
                   drop: tuple = ()) -> None:
    fixtures = make_fixtures()
    for name, patch in (mutations or {}).items():
        fixtures[name].update(patch)
    for name in drop:
        fixtures.pop(name, None)
    for name, data in fixtures.items():
        (tmp_path / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_gate(tmp_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp_path,
                          capture_output=True, text=True, timeout=60)


def _expect_fail(tmp_path, expect: str, **kw) -> None:
    write_fixtures(tmp_path, **kw)
    r = run_gate(tmp_path)
    assert r.returncode == 1, f"应被拒收: {expect}\nstderr:\n{r.stderr}"
    assert expect in r.stderr


# ── 结构校验逐分支 ────────────────────────────────────────────────────────
def test_missing_version_json_rejected(tmp_path):
    _expect_fail(tmp_path, "缺少 version.json", drop=("version.json",))


def test_bad_semver_rejected(tmp_path):
    _expect_fail(tmp_path, "非法 SemVer",
                 mutations={"version.json": {"versionName": "1.2"}})


def test_tag_mismatch_rejected(tmp_path):
    _expect_fail(tmp_path, "与 v1.2.3 不一致",
                 mutations={"version.json": {"tag": "v9.9.9"}})


def test_bad_version_code_rejected(tmp_path):
    _expect_fail(tmp_path, "versionCode 应为正整数",
                 mutations={"version.json": {"versionCode": 0}})


def test_patches_schema_rejected(tmp_path):
    _expect_fail(tmp_path, "patches.json.schema 应为 abyss-patches-v1",
                 mutations={"patches.json": {"schema": "abyss-patches-v2"}})


def test_latest_tag_mismatch_rejected(tmp_path):
    _expect_fail(tmp_path, "不一致",
                 mutations={"patches.json": {"latestTag": "v1.1.0"}})


def test_duplicate_patch_segment_rejected(tmp_path):
    fixtures = make_fixtures()
    seg = fixtures["patches.json"]["patches"][0]
    fixtures["patches.json"]["patches"].append(dict(seg))
    for name, data in fixtures.items():
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    r = run_gate(tmp_path)
    assert r.returncode == 1
    assert "重复补丁段" in r.stderr


def test_changelog_history_top_is_current_rejected(tmp_path):
    _expect_fail(tmp_path, "不应为本版",
                 mutations={"changelog.json": {"history": [
                     {"versionName": "1.2.3", "tag": "v1.2.3", "title": "dup", "notes": ["- n"]}]}})


# ── N-SEC-001 断言 A：签名强制与错签拒收 ─────────────────────────────────
def test_valid_but_unsigned_rejected(tmp_path):
    # 结构全绿但 .minisig 缺失 → 门禁必须红（N-SEC-001 起签名强制）
    write_fixtures(tmp_path)
    r = run_gate(tmp_path)
    assert r.returncode == 1
    assert ".minisig 缺失" in r.stderr


def test_wrong_key_signature_rejected(tmp_path):
    # 用生成密钥（非 TRUSTED_PUBKEYS）签出的「合法格式」签名必须被拒
    pytest.importorskip("nacl")
    sys.path.insert(0, str(TOOLS))
    import nacl.signing
    import minisign_py

    write_fixtures(tmp_path)
    key = nacl.signing.SigningKey.generate()
    pub = bytes(key.verify_key)
    pubkey_text = ("untrusted comment: test key\n"
                   + base64.b64encode(b"Ed" + b"12345678" + pub).decode("ascii") + "\n")
    seed, keynum, _ = minisign_py.load_seed(
        base64.b64encode(bytes(key)).decode("ascii"), pubkey_text)
    for name in ("version.json", "patches.json", "changelog.json"):
        raw = (tmp_path / name).read_bytes()
        sig = minisign_py.sign_message(seed, keynum, raw, "u", "t")
        (tmp_path / f"{name}.minisig").write_text(sig, encoding="ascii")
    r = run_gate(tmp_path)
    assert r.returncode == 1
    assert "验签失败" in r.stderr
