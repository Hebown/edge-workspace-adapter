# 调查环境

| 项目 | 值 |
|---|---|
| 操作系统 | Windows（Win32 shell） |
| Edge | 158.0.4370.45（`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`） |
| Profile | `Local State` 中列出的实际使用 Profile；`scan` 会打印它的完整路径 |
| 工作区同步 | 已启用（`sync.has_been_enabled` + `sync.edge_workspaces`） |
| Python | 3.10+，仅标准库；测试使用 3.14 |
| 测试副本 | 用 `tools/make_test_profile.py` 从真实 Profile 复制，从不把副本当作交付物 |

注意：

1. 不要假设一定是 `Default` Profile。先跑 `scan`，确认它列出的 profile 路径。
2. `edge://version` 是人工核对 Profile 路径的权威方式；脚本以 `Local State` 的
   `profile.last_used` 为默认，可用 `--profile-dir` 覆盖。
3. Edge 运行时不要写 LevelDB；`scan` 只读且先复制，因此可以安全运行。
4. 本仓库不含任何真实 Profile 数据、账号名、工作区名称或 GUID。
