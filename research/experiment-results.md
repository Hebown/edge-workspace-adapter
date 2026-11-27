# 逆向与实验记录（脱敏版）

环境：Windows，Edge `158.0.4370.45`，实际使用 Profile 由 `Local State` 指定，Python 3.14（仅标准库）。
所有 GUID / 工作区名称 / 账号路径均已替换为占位符，字节长度与结构保持可复算。

---

## E1 数据源定位

在整个 `User Data` 目录里用一个已知工作区 GUID（UTF-8 与 UTF-16LE）搜索，命中位置：

| 命中文件 | 说明 |
|---|---|
| `Default\Sync Data\LevelDB\*.log` / `*.ldb` | 工作区实体本体 |
| `Default\Preferences.bak` | 历史偏好备份 |
| `Default\Sessions\Session_*` | 会话恢复记录 |
| `Default\JumpListIconsRecentWorkspacesV2\*.ico` | 图标文件名中含该 GUID |

`Default\Workspaces\` 目录包含 `Logs`、`Collaborators`；`WorkspacesCache` 未出现。

【事实】配置源为 `Sync Data/LevelDB`，任务栏图标目录承担渲染缓存角色。

## E2 LevelDB 读取器的三个关键点

1. `.log` 是 WriteBatch：12 字节头（`sequence:uint64` + `count:uint32`），随后每条为
   `tag:byte` + `key_len:varint` + `key` +（tag=1 时）`value_len:varint` + `value`；`tag=0` 表示删除。
2. 本机 `.ldb` 的 `BlockHandle.size` 覆盖 payload，读取时按 `size+5` 取值（type + crc32c）；
   键为 internal key，末尾 8 字节是 `(sequence << 8 | type)` 小端。
3. 同一 key 在 `.ldb` 中存在多个版本，按 sequence 取最新值；`.log` 中的新值优先级更高。

按这三点实现后，读取结果为 17 个工作区。

## E3 记录形状

`edge_workspace-dt-<id>` 里混着两类实体，靠 `specifics.field4 / field5` 区分：

| 形状 | 数量 | field4 | field5 |
|---|---|---|---|
| 工作区 | 17 | `{1:name, 2:ARGB颜色, 3:最近使用µs, 6:共享标记, 9:emoji?}` | — |
| 标签页 | 188+ | — | `{1:父工作区id, 3:url, 4:标题, 5:favicon}` |

其中 1 个工作区带 `details.field9`，值为 UTF-8 `F0 9F 93 81`（U+1F4C1 📁）；其余 16 个的 details 无 field9。
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
- 启动 Edge 20 秒后关闭：17 个工作区全部保留，0 个带 emoji；leveldb 完成压缩后新值生效。

【事实】新日志由 Edge 正常回放，数据库结构保持完整。

## E6 一次对照实验（排除误判）

第一版实验给副本的启动命令附加了被 PowerShell 破坏的网络参数，窗口标题出现 `%2A`，
关闭后 709 个 `edge_workspace` key 全部变成删除标记。为排除写入机制的影响，做对照：

| 副本 | 是否修改 | 启动参数 | 结果 |
|---|---|---|---|
| A | 是 | 带异常参数 | 17 → 0 个工作区 |
| B | 否 | 正常 | 仍有 17 个工作区 |
| C | 是 | 正常 | 仍有 17 个工作区，0 个 emoji |

【事实】异常启动参数与断网状态触发了清空；C 证明写入机制本身保持数据完整。

## E7 真实 Profile 应用与重启

```
apply --workspace "<name>" --icon default
backup : <LOCALAPPDATA>\edge-workspace-adapter\backups\backup-<timestamp>
log    : <profile>\Sync Data\LevelDB\012168.log
```

重启 Edge 后再次 `scan`：目标工作区显示 `DEFAULT` 且 `field9` 已删除；其余 16 个工作区名称、
颜色、sync version 保持原值；sync version 保持原值，表明本次改动留在本机。

两次快照的机器可读差异只有一行：`~ <name>: emoji '📁' -> None`。

## 未完成 / 可测

- 【可测】在另一台已登录同一账号的设备上修改目标工作区的图标，等本机同步，检查 emoji 是否恢复。
- 【可测】`details.field9 = ""`（空串）的渲染结果需要独立实验。
- 【推断】让 Edge 自己提交一次（见 `agent.md` 第 2 节策略 2）能持久化到服务器；尚未实测。
- 【推断】`edge://flags` 的 `msEdgeSpaceworksEmoji` 属于全局功能开关，适用于全局配置场景。
