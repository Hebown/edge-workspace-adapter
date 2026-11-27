# 给使用者 / Agent 的运行说明

这个文件回答三件事：**适配器怎么跑起来**、**服务器覆盖怎么办**、**Edge 版本变了怎么办**。
读完之后按第 4 节的顺序操作即可。

---

## 1. 它是怎么运行的

适配器不是浏览器扩展、不是常驻服务，而是一个**按需执行的命令行工具**，只用 Python 3.10+ 标准库。

```
读路径（Edge 可以开着）
  scan / preview / snapshot / diff / verify
        └─ 把 Sync Data/LevelDB 复制到临时目录 -> 只读解析 -> 删除临时目录

写路径（必须先完全退出 Edge）
  apply / restore
        └─ 先整目录备份 -> 往 LevelDB 追加一个新 .log -> 重读校验 -> Edge 下次启动时回放
```

关键点：

- **读永不碰原库**：永远先复制再解析，所以 `scan` 可以在浏览器运行时执行。
- **写永不改旧文件**：`.ldb` / `MANIFEST` / `CURRENT` 一概不动，只新增一个日志；删掉它就是回滚。
- **改的是一个字段**：`edge_workspace-dt-<id>` → `specifics.field4` → `details.field9`（emoji 字符串）。
  删掉该字段，Edge 自己渲染内置线框；字段存在则按其内容渲染 emoji。
- **生效时机**：写入后不会热更新，必须重启 Edge。

### 1.1 最常用命令

在项目目录执行（`python` 换成你本机可用的解释器）：

```powershell
python adapter\cli.py scan
python adapter\cli.py preview --workspace "<工作区名称>" --icon default
python adapter\cli.py apply  --workspace "<工作区名称>" --icon default
# 重启 Edge 之后
python adapter\cli.py verify --workspace "<工作区名称>"
python adapter\cli.py diff --before <前快照.json> --after <后快照.json>
python adapter\cli.py restore --backup <备份目录>
```

`--profile-dir` 可指定非 Default 的 Profile（先用 `scan` 看它列出哪些 profile）。
`--icon` 可以是 `default`，也可以是任意 emoji 字符串。
`--allow-unknown` 和 `--force` 只用于诊断，**不要在日常使用中添加**。

### 1.2 如何 customize 自己的运行方式

| 需求 | 做法 |
|---|---|
| 一次处理多个工作区 | 循环调用 `apply`；每次调用都会各自备份并各自校验。需要更强的事务性时，把目标写成一个列表并在外层脚本里先逐个 `preview` 再逐个 `apply`。 |
| 换成别的目标图标 | `--icon "📁"` 等；`default` 是适配器内部表达的目标状态，不是 Edge 的配置值。 |
| 换 Profile | `--profile-dir "%LOCALAPPDATA%\Microsoft\Edge\User Data\Profile 1"`。 |
| 改备份位置 | 备份默认写到 `%LOCALAPPDATA%\edge-workspace-adapter\backups`；用 `--backup-dir` 覆盖。**不要把备份放进要上传的仓库目录。** |
| 自动化 / 定时 | 写一个 PowerShell 包装脚本：先检测 `msedge.exe` 已退出，再调用 `apply`，最后记录退出码。读操作无需停机。 |
| 接入 Agent | 把 `scan` 的输出作为观察，`preview` 作为计划，`apply` 作为需要确认的动作，`verify` 作为验收；任何时候都可以通过 `restore` 回退。 |
| 支持新版本 Edge | 按第 3 节更新 `adapter/layout.py`，再补一条实验记录。 |

---

## 2. 服务器上的图标更权威，怎么办

这里必须区分两种“权威”：

- **本地权威**：Edge 界面**当前**渲染什么，完全由本地 LevelDB 决定。我们改的就是它，重启后立刻生效。
- **跨设备权威**：同步服务器保存的是账号级状态。适配器的修改**不会主动上传**，因为 metadata 里的服务器版本没有变。所以：
  - 只要服务器不主动更新这个实体，本地改动会一直保持（已实测：重启、同步提示后仍在）。
  - 一旦服务器版本前进（其他设备改了该工作区、重新登录触发全量下载），emoji 会被重新下载，**本地改动被覆盖**。

### 推荐的三档策略（按风险从低到高）

1. **本地覆盖（默认，零风险）**
   直接用 `apply`。把它当作“本机显示偏好”，接受云端可能恢复。适合临时、单设备场景。

2. **让 Edge 自己提交一次（推荐给想持久化的用户）**
   不要伪造同步 metadata —— 那会导致实体被重置，风险远大于收益。
   正确做法是利用 Edge 自己的写入路径：

   ```
   apply（Edge 关闭时改好本地 specifics）
     -> 启动 Edge，此时内存中的工作区已带“无 emoji”状态
     -> 在该工作区上做一次无害的 UI 改动（改名再改回来、开关一次标签页等）
     -> Edge 会以正确的 metadata 把整份 specifics 提交到服务器
     -> 等待同步完成后，用另一台设备或重新登录验证
   ```

   【推断，尚未实测】这条链路依赖“任何本地改动都会提交整份 specifics”。它不会破坏 metadata，
   失败时也只是回到策略 1。验证方法见 `research/experiment-results.md` 的「可测」条目。

3. **守护式重放（兜底）**
   如果第 2 条不可用，可以在每次登录、Edge 启动前跑一次包装脚本重新 `apply`。
   它是补偿手段，不是根治：同步发生在浏览器运行期间，下次登录前才会被纠正。

**明确不做的事**：不关闭用户同步、不删除 `-md-` metadata、不猜 sequencing 字段、不修改服务端数据。

---

## 3. Edge 版本变了 / 字段位置变了怎么办

protobuf 的字段号是 Edge 内部实现，不是公开 API；不能假设 158 的布局永远有效。

### 3.1 已经落地的护栏

`adapter/layout.py` 维护一张**实测过的布局表**。每条布局同时记录：

- Edge 主版本号；
- 结构签名（外层与 details 里各字段的 wire type）；
- 实际的字段号（details / emoji / name / color）。

`scan` 会打印当前 `layout` 状态：

- `known`：版本和结构都匹配 → 可写。
- `shape-compatible`：版本没见过，但结构一致 → 可写，建议补一条布局记录。
- `unknown`：**`apply` / `preview` 直接拒绝写入**，除非显式传 `--allow-unknown`。

这保证 Edge 改版后不会“静默改错字段”。

### 3.2 升级到新 Edge 版本的流程

1. 先在**新版本**上跑 `scan -v`，确认仍能列出工作区、图标列正常。
2. 看输出的 `layout`：
   - `known`：无需改动。
   - `shape-compatible`：在 `layout.py` 的 `edge_major` 里加上新主版本号，补一条实验记录。
   - `unknown`：先用 `scan -v` 观察 details 结构，找出 emoji 字段（UTF-8 string、内容是 emoji），
     新增一条布局记录并做一次副本实验，再用于真实 Profile。
3. 跑 `preview` 确认 `field = details.N` 指向正确字段。
4. 才允许 `apply`。

### 3.3 兼容性维护策略（明确的边界）

- **维护**：当前实测版本（Edge 158）以及任何已经写入布局表、并有实验记录的版本。
- **不维护**：未记录布局的 Edge 版本；工具会拒绝写入而不是猜测。
- **代价**：Edge 大版本升级后需要人做一次约 10 分钟的确认；这是为了避免误改用户数据而刻意选择的保守策略。
- **可测**：`layout.py` 的表是可编辑的，加一行即扩展支持；不需要改解析代码。

---

## 4. 安全底线

1. `apply` 前必须关闭所有 `msedge.exe`；工具会检查，除非显式 `--force`。
2. 每次写入前自动备份完整 `Sync Data/LevelDB` 与 `Preferences`。
3. 一次只改一个工作区，其他字段原样保留。
4. 写入后立刻重读校验；不一致就报错。
5. 任何时刻都能 `restore`，或删除新增的那个 `.log` 文件。
6. 不在仓库里存放真实 Profile 数据、备份、账号信息。
