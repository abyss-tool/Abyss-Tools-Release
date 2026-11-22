# 热更新体系手册（HOT_UPDATE.md）

> 发布仓侧手册。对齐 `Ultra-Guru/Android-Guru-Agent-Release` 的热更新体系设计；
> 客户端契约与规范见开发仓 `docs/UPDATE_CHANNEL.md`。
> 基线：v0.10（M1）—— 通道清单 detached 签名已落地（N-SEC-001）。

## 1. 通道文件（本仓 main 分支根，客户端检查更新的固定读取点）

| 文件 | 作用 | 签名 |
| --- | --- | --- |
| `version.json` | 最新版本 + `download{url,sizeBytes,sha256}` + `patch`（增量档，可 null）+ `commitSha` | ✅ `version.json.minisig` |
| `patches.json` | 跨版本链式增量索引（`latestTag` + `patches[]`） | ✅ `patches.json.minisig` |
| `changelog.json` | 版本叙事（latest 置顶 + history 下沉 ≤20 条） | ✅ `changelog.json.minisig` |
| `plugins.json`（插件中心仓） | 3 个引擎级插件聚合索引 | ✅ `plugins.json.minisig` |
| `abyss-plugin-*/patches/index.json`（插件仓） | 插件补丁通道 | ✅ `index.json.minisig` |

**信任链（v0.10 起，领先项）**：全部清单附带 minisign 兼容 detached 签名
（Ed25519，公钥 `meng4117222` 内置客户端 `ChannelSignatureVerifier.TRUSTED_KEYS`）；
发布流水线对**写入字节**签名、清单与 `.minisig` 同 job 原子提交、写后回读自验。
客户端**先验签再解析**，无签名一律 fail-closed 拒绝 —— 清单与签名字节级配对，
镜像劫持最多造成"下载失败"，不可能注入被篡改的清单。

## 2. 发布流水线（全自动，双仓模式）

```
开发仓 PR 合并（push main）
  └ auto-release.yml：版本推进（AppInfo 单一事实源，未发布名原样采用 /
     已发布名 patch 自增；versionCode 恒 = 通道现值 + 1）
      └ Prepare manifest signing keys（RELEASE_SIGNING_KEY secret，缺失即拒）
      └ assembleRelease（keystore meng411722 同签名 + apksigner 指纹门禁）
      └ publish_release.py：
          ├ versionCode 单调门禁（防旧版本拉回 latest）
          ├ APK 上传 Release 资产（幂等：同名先删）+ 回读 digest 比对（fail-closed）
          ├ 三件套清单内存签名 → 清单与 .minisig 相邻原子提交
          └ 写后自检：回读清单 + 回读 .minisig 验签（清单↔签名逐字节配对）
```

tag 触发的手工稳定发布（`release.yml`）并存，同一套签名门禁。

## 3. 客户端决策表（core:update UpdateChecker）

| 条件 | 结果 |
| --- | --- |
| 验签失败 / `.minisig` 缺失 | **Failed（fail-closed，人话提示"镜像可能尚未同步"）** |
| `latest <= current` | UpToDate |
| `latest > current` 且 `patch.fromTag == 当前 tag` | Available（**增量**） |
| `latest > current` 其余情形 | Available（整包 / 资产未发布） |
| 下载后 SHA-256 不符 | Failed（拒绝安装，摘要缺失即拒） |

安装闭环：PackageInstaller 同签名门禁 + 发布者指纹硬校验
（`PublisherSignatures.PINNED_SHA256`）+ 未知来源确认页转发。

## 4. 数据补丁（abyss-patch-v1，已可用）

插件 manifest / 技能目录 / 配置等数据资产的增量：下载 → SHA-256 →
**备份 → 应用 → 失败自动回滚**（ZipPatchApplier：路径穿越 + zip 炸弹 +
根白名单三重门，载荷缺失整包拒绝）。

## 5. 下载镜像（v0.7.0 起）

ghfast.top / gh-proxy.com / ghproxy.cn 等 + GitHub 直连兜底。
**镜像只做通路不做信任源**：域白名单（FetchHostPolicy，PREFIX 递归校验
内层）+ 一切资产强制 SHA-256 + 清单验签不依赖镜像诚实。失败冷却 +
自动换链，单镜像死亡不阻塞。

## 6. 对齐状态与路线图

| 能力 | Android-Guru-Agent-Release | 本仓 |
| --- | --- | --- |
| 双仓发布 + 清单滚动 + 单调门禁 | ✅ | ✅ 同构 |
| 清单 detached 签名（客户端先验签） | —（未披露） | ✅ **v0.10 落地（领先项）** |
| vcdiff 二进制增量 | ✅ 已落地 | ⏳ 规划（`N-UPD-001`，patches.json 结构已就绪） |
| 数据级热更通道（hot 档 / 应急热修工作流） | ✅ apex-hot-v1 | ⏳ 规划（`N-UPD-002` 灰度通道一并评估） |
| variants 下载档（arm64/universal） | ✅ | ⏳ 单 universal（按需评估） |
| commitSha 追溯 | ✅ | ✅（version.json.commitSha） |

> 诚实边界：vcdiff 与热更通道**未实现**，本手册不虚标;清单验签为本仓
> 已落地的信任链加固，`SECURITY.md` 有完整兼容/灰度策略。
