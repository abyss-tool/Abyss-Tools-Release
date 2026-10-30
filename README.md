# Abyss-Tools-Release —— 深渊工具发布仓库

[![Manifests](https://github.com/Ultra-Guru/Abyss-Tools-Release/actions/workflows/validate-manifests.yml/badge.svg?branch=main)](https://github.com/Ultra-Guru/Abyss-Tools-Release/actions/workflows/validate-manifests.yml)

双仓库模式的**发布侧**：开发仓库 [Ultra-Guru/Abyss-Tools](https://github.com/Ultra-Guru/Abyss-Tools) 的 CI 在此发布版本资产；App 客户端把本仓库 main 分支根作为**检查更新的固定读取点**。

## 通道资产

| 文件 | 角色 |
| --- | --- |
| `version.json` | 版本清单：versionName / versionCode / tag / download / patch（客户端 `UpdateChecker` 固定读取点） |
| `patches.json` | 补丁全量索引：跨版本链式增量底座 |
| `changelog.json` | 版本叙事：设置页 / 更新弹层消费 |
| GitHub Releases | APK（v0.2 起）与增量补丁资产 |

## 当前状态：v0.1.0 框架预览

- 通道清单已建立并通过 CI 门禁；
- `download` / `patch` 为 null：APK 与二进制增量资产自 v0.2 发布流水线起发布；
- 客户端行为：检查更新 → 读取 version.json → 「资产未发布」人话提示（fail-closed）。

## 发布流水线（v0.2 接入）

```
开发仓 PR 合并 → CI 发布（release.yml）
    ├─ 打 tag v* → 构建 release APK（固定签名）
    ├─ 与上一版 APK 做 vcdiff 增量补丁
    ├─ 上传 GitHub Releases 资产
    └─ 写回本仓库 version.json / patches.json / changelog.json
```

签名纪律：发布签名将固定为一份入库 keystore（对齐 Android-Guru-Agent
v1.4.8 签名漂移根因修复），保证增量合成 APK 与已装 APK 签名一致，覆盖
安装零冲突。

## 数据补丁（已可用）

插件 manifest / 技能目录 / 配置层的数据资产走 `abyss-patch-v1` 数据补丁
通道（各插件仓 `patches/index.json`），不经过本仓库 —— 详见开发仓
`docs/UPDATE_CHANNEL.md`。
