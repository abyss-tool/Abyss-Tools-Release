# Abyss-Tools-Release —— 深渊工具发布仓库

[![Manifests](https://github.com/Ultra-Guru/Abyss-Tools-Release/actions/workflows/validate-manifests.yml/badge.svg?branch=main)](https://github.com/Ultra-Guru/Abyss-Tools-Release/actions/workflows/validate-manifests.yml)

双仓库模式的**发布侧**：开发仓库 [Ultra-Guru/Abyss-Tools](https://github.com/Ultra-Guru/Abyss-Tools) 的 CI 在此发布版本资产；App 客户端把本仓库 main 分支根作为**检查更新的固定读取点**。

## 通道资产

| 文件 | 角色 |
| --- | --- |
| `version.json` | 版本清单：versionName / versionCode / tag / download / patch（客户端 `UpdateChecker` 固定读取点） |
| `patches.json` | 补丁全量索引：跨版本链式增量底座 |
| `changelog.json` | 版本叙事：设置页 / 更新弹层消费 |
| GitHub Releases | APK 资产（v0.1.1 起自动发布）与增量补丁资产（v0.2 起） |

## 当前状态：v0.1.1 起全自动发布

- `release.yml`（开发仓 tag `v*` 触发）自动完成：构建入库 keystore 签名的 release APK → 本仓库创建 GitHub Release + 上传 APK 资产 → 滚动 `version.json` / `patches.json` / `changelog.json`；
- 客户端行为：检查更新 → 读取 version.json → 发现新版本 → 下载 APK → SHA-256 校验 → PackageInstaller 安装（同签名门禁恒定通过）；
- APK 二进制增量（vcdiff）仍按路线图于 v0.2 接入 —— 当前补丁链记录于 `patches.json`，数据补丁走插件仓通道。

## 发布流水线（已上线）

```
开发仓升版（build.gradle.kts ↔ AppInfo 三处同步，CI 门禁）
    └─ git tag v* && git push --tags
         └─ release.yml：assembleRelease（keystore/abyss-release.jks 恒定签名）
              ├─ tools/publish_release.py（RELEASE_TOKEN）
              │    ├─ 本仓库创建 GitHub Release（v<版本>）+ APK 资产
              │    ├─ version.json：download{url,sizeBytes,sha256} + notes
              │    ├─ patches.json：latestTag 滚动
              │    └─ changelog.json：旧 latest 下沉 history，新版本置顶
              └─ 发布要点：docs/release-notes/v<版本>.md（一行一条）
```

签名纪律：发布签名固定为开发仓入库 keystore `keystore/abyss-release.jks`
（Termux / F-Droid 同款做法），指纹恒定 —— 覆盖安装与后续增量补丁零签名
冲突；`ABYSS_KEYSTORE_*` 环境变量可覆盖（CI secret 注入场景）。
## 数据补丁（已可用）

插件 manifest / 技能目录 / 配置层的数据资产走 `abyss-patch-v1` 数据补丁
通道（各插件仓 `patches/index.json`），不经过本仓库 —— 详见开发仓
`docs/UPDATE_CHANNEL.md`。
