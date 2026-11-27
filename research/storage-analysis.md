# 实际数据源 vs 缓存

结论先行：**权威本地配置在 Sync Data LevelDB；任务栏图标目录只是渲染结果。**

| 位置 | 角色 | 依据 |
|---|---|---|
| `Default\Sync Data\LevelDB` | **本地权威配置**（同步模型的持久层） | 全盘搜索工作区 GUID 只命中这里、跳转列表和一个会话文件；改这里的字段并重启，图标随之改变 |
| `edge_workspace-dt-<id>` | 工作区 / 标签页实体 | 工作区实体的 `specifics.field4` 含名称、颜色、图标；标签页实体用 `field5` 含 url/标题/favicon |
| `edge_workspace-md-<id>` | 同步 metadata | 保存服务器 id、版本、时间戳；适配器不修改它 |
| `Default\JumpListIconsRecentWorkspacesV2\*.ico` | **缓存**（渲染结果） | 文件名含颜色与 emoji 变体；删掉后 Edge 可按配置重新生成；改它不影响配置 |
| `Default\Workspaces\` | 会话协作数据 | 包含 `Logs`、`Collaborators`；`WorkspacesCache` 未在该目录出现 |
| `Preferences` / `Secure Preferences` | 同步开关与 UI 偏好 | 决定 workspace sync 是否启用，不保存单个工作区的图标 |
| `Local State` | Profile 索引 | 用于定位实际 Profile |

【事实】受测版本的 `Workspaces\` 目录包含 `Logs` 与 `Collaborators`；配置定位以全盘搜索结果为准。

【事实】一个 GUID 在全盘只出现在上述位置，因此不存在“另有一份 JSON 配置”的证据。

【推断】服务器保存账号级副本；跨设备冲突时服务器版本可能胜出。详见 `agent.md` 第 2 节。
