# 逆向与实验记录（脱敏版）

环境：Windows，Edge `158.0.4370.45`，实际使用 Profile 由 `Local State` 指定，Python 3.14（仅标准库）。
所有 GUID / 工作区名称 / 账号路径均已替换为占位符，但字节长度和结构保持可复算。

---

## E1 数据源定位

在整个 `User Data` 目录里用一个已知工作区 GUID（UTF-8 与 UTF-16LE）搜索，命中位置：

| 命中文件 | 说明 |
|---|---|
| `Default\Sync Data\LevelDB\*.log` / `*.ldb` | 工作区实体本体 |
| `Default\Preferences.bak` | 历史偏好备份 |
| `Default\Sessions\Session_*` | 会话恢复记录 |
| `Default\JumpListIconsRecentWorkspacesV2\*.ico` | 图标文件名中含该 GUID |

`Default\Workspaces\` 下只有 `Logs`、`Collaborators`，没有 `WorkspacesCache`。

【事实】配置源是 `Sync Data/LevelDB`，任务栏图标目录只是渲染缓存。

## E2 LevelDB 读取器的三个坑

1. `.log` 是 WriteBatch：12 字节头（`sequence:uint64` + `count:uint32`），随后每条为
   `tag:byte` + `key_len:varint` + `key` +（tag=1 时）`value_len:varint` + `value`；`tag=0` 为删除。
2. 本机 `.ldb` 的 `BlockHandle.size` 不含 5 字节块尾（type + crc32c），按 `size+5` 读才正确；
   键为 internal key，末尾 8 字节是 `(sequence << 8 | type)` 小端。
3. 同一 key 在 `.ldb` 中会存在多个版本，必须按 sequence 取最新；`.log` 中的新值覆盖 `.ldb`。

不修这三点只读得到 1 个工作区；修好后是 17 个。

## E3 记录形状

`edge_workspace-dt-<id>` 里混着两类实体，靠 `specifics.field4 / field5` 区分：

| 形状 | 数量 | field4 | field5 |
|---|---|---|---|
| 工作区 | 17 | `{1:name, 2:ARGB颜色, 3:最近使用µs, 6:共享标记, 9:emoji?}` | — |
| 标签页 | 188+ | — | `{1:父工作区id, 3:url, 4:标题, 5:favicon}` |

只有 1 个工作区带 `details.field9`，值为 UTF-8 `F0 9F 93 81`（U+1F4C1 📁）；其余 16 个没有该字段。
这与“部分工作区仍是旧版线框图标”的观察一致。

## E4 emoji 的字节位置（脱敏样例）

把工作区名称替换成等长的 12 字节 `WorkspaceOne`（原始样例为 12 字节中文名）：

```
08 01
12 5D
  0A 24 <36 字节 GUID>
  10 <8 字节 创建时间 µs>
  18 <8 字节 修改时间 µs>
  22 23                        details，35 字节
    0A 0C 57 6f 72 6b 73 70 61 63 65 4f 6e 65   "WorkspaceOne"
    10 00                        颜色 = 0
    18 <8 字节 最近使用>
    30 01                        共享标记
    40 00
    4A 04 F0 9F 93 81          ← field9 = 📁
1A 02 08 00
```

删除 `4A 04 F0 9F 93 81` 并把两级长度收缩：`5D→57`（93→87）、`23→1D`（35→29），
总长 101→95 字节。

## E5 写入机制验证（副本）

- 复制 Profile → `apply --force` → 新增 `012168.log`（1 条 WriteBatch，seq = max_seq+1）。
- 立刻重读：该记录的 `details.field9` 已消失。
- 启动 Edge 20 秒后关闭：17 个工作区全部仍在，0 个带 emoji；leveldb 完成压缩后旧值被新值取代。

【事实】新日志可被 Edge 正常回放，不破坏数据库。

## E6 一次对照实验（排除误判）

第一版实验给副本的启动命令附加了被 PowerShell 破坏的网络参数，窗口标题出现 `%2A`，
关闭后 709 个 `edge_workspace` key 全部变成删除标记。为排除“写入导致清空”，做对照：

| 副本 | 是否修改 | 启动参数 | 结果 |
|---|---|---|---|
| A | 是 | 带异常参数 | 17 → 0 个工作区 |
| B | 否 | 正常 | 仍有 17 个工作区 |
| C | 是 | 正常 | 仍有 17 个工作区，0 个 emoji |

【事实】清空由异常启动参数/断网状态引起，与写入机制无关；C 是有效对照。

## E7 真实 Profile 应用与重启

```
apply --workspace "<name>" --icon default
backup : <LOCALAPPDATA>\edge-workspace-adapter\backups\backup-<timestamp>
log    : <profile>\Sync Data\LevelDB\012168.log
```

重启 Edge 后再次 `scan`：目标工作区显示 `DEFAULT` 且 `field9` 不存在；其余 16 个工作区名称、
颜色、sync version 均未变化；sync version 未前进，说明没有新的上传。

两次快照的机器可读差异只有一行：`~ <name>: emoji '📁' -> None`。

## 未完成 / 可测

- 【可测】在另一台已登录同一账号的设备上修改目标工作区的图标，等本机同步，看 emoji 是否被恢复。
- 【可测】`details.field9 = ""`（空串）是回退还是空白；本机没有这种样本。
- 【推断】让 Edge 自己提交一次（见 `agent.md` 第 2 节策略 2）能持久化到服务器；尚未实测。
- 【推断】`edge://flags` 的 `msEdgeSpaceworksEmoji` 是全局功能开关，影响所有工作区，不用于单工作区回退。
