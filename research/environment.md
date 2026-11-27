# 调查环境

| 项目 | 值 |
|---|---|
| 操作系统 | Windows（Win32 shell） |
| Edge | 158.0.4370.45（`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`） |
| Profile | `Local State` 中列出的实际使用 Profile；`scan` 会打印它的完整路径 |
| 工作区同步 | 已启用（`sync.has_been_enabled` + `sync.edge_workspaces`） |
| Python | 3.10+，仅标准库；测试使用 3.14 |
| 测试副本 | 用 `tools/make_test_profile.py` 从真实 Profile 复制，副本仅用于实验 |

注意：

1. Profile 路径以 `scan` 输出为准；脚本默认读取 `Local State` 的 `profile.last_used`。
2. `edge://version` 是人工核对 Profile 路径的方式；`--profile-dir` 可覆盖脚本的默认值。
3. 写入操作在 Edge 退出后执行；`scan` 先复制再解析，可在浏览器运行时执行。
4. 本仓库不含任何真实 Profile 数据、账号名、工作区名称或 GUID。
