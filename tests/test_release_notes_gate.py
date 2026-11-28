"""validate_release_notes.py（N-ENG-010 发布说明质量门禁）常驻单测。

直接模块导入（脚本有 __main__ 守卫，导入无副作用），逐分支覆盖
validate() 的 fail-closed 出口与正例放行。
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import validate_release_notes as gate  # noqa: E402

GOOD_NOTES = (
    "- 新增：设置分区重构，签名 secret 状态可视化\n"
    "- 修复：publish_release 的 minisig 更新竞态（PR #18）\n"
    "- 优化：通道核验切换 contents API，绕开 raw CDN 缓存\n"
)


def _expect_fail(notes: str, version: str = "0.9.18") -> str:
    """断言 validate() 以 SystemExit(1) 拒收，并返回 stderr 供子串断言。"""
    with pytest.raises(SystemExit) as exc:
        gate.validate(notes, version)
    assert exc.value.code == 1


# ── 正例 ─────────────────────────────────────────────────────────────────
def test_good_notes_pass(capsys):
    gate.validate(GOOD_NOTES, "0.9.18")
    out = capsys.readouterr()
    assert "✅" in out.out
    assert "3 条要点" in out.out


def test_breaking_change_in_first_bullet_passes():
    notes = (
        "- BREAKING: 目标 SDK 升级需整组联动，升级注意先备份\n"
        "- 新增：双执行域探测\n"
        "- 修复：会话恢复\n"
    )
    gate.validate(notes, "1.0.0")  # 不抛即放行


# ── 反例（N-ENG-010 规约 1~5 逐条）───────────────────────────────────────
def test_empty_notes_rejected():
    _expect_fail("   \n  ")


def test_too_short_rejected():
    _expect_fail("- a\n- b\n- c")


def test_pr_merge_title_as_notes_rejected():
    notes = "Merge pull request #18 from abyss-tool/ci-x\n- a\n- b\n- c\n"
    _expect_fail(notes)


def test_too_few_bullets_rejected():
    _expect_fail("- 只有两条要点\n- 第二条")


def test_too_long_rejected():
    _expect_fail("- " + "x" * 4001)


def test_breaking_keyword_not_in_first_bullet_rejected():
    # 关键词表为「声明形态」（B-05 精确化）：裸「不兼容」不触发，
    # 「升级注意」等声明性用语才触发首条要点强制
    notes = (
        "- 新增：常规功能\n"
        "- 升级注意：需先卸载旧版再安装\n"
        "- 优化：性能\n"
    )
    _expect_fail(notes)


def test_placeholder_rejected():
    notes = "- 新增 XX\n- 修复 TODO\n- 优化 ZZ\n"
    _expect_fail(notes)


# ── 入口分支（--markdown / changelog 结构化 notes）────────────────────────
def test_markdown_mode_passes(tmp_path, capsys):
    md = tmp_path / "v0.9.18.md"
    md.write_text(GOOD_NOTES, encoding="utf-8")
    assert gate.main(["prog", "--markdown", str(md)]) == 0
    assert "✅" in capsys.readouterr().out


def test_markdown_mode_bad_filename_rejected(tmp_path):
    md = tmp_path / "release.md"
    md.write_text(GOOD_NOTES, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        gate.main(["prog", "--markdown", str(md)])
    assert exc.value.code == 1


def test_changelog_structured_notes_joined(tmp_path):
    data = {"latest": {"versionName": "0.9.18", "tag": "v0.9.18",
                       "notes": ["- 新增 A", "- 修复 B", "- 优化 C"]}}
    p = tmp_path / "changelog.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    notes, version = gate.load_latest_from_changelog(p)
    assert version == "0.9.18"
    assert notes == "- 新增 A\n- 修复 B\n- 优化 C"
    gate.validate(notes, version)  # 结构化数组 join 后应整体放行
