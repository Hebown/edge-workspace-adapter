# 工作区记录的 protobuf 结构

所有字段号来自对 Edge 158 的逐字节解码；占位 GUID/名称已脱敏。

```
edge_workspace-dt-<workspace-id>            key
└─ value
   ├─ field1 = 1                            varint，固定标记
   ├─ field2 = EdgeWorkspaceSpecifics       message
   │  ├─ field1 = "<workspace-id>"           string，与 key 后缀一致
   │  ├─ field2 = 创建时间                   varint，µs since 1601-01-01
   │  ├─ field3 = 修改时间                   varint，同上
   │  └─ field4 = WorkspaceDetails           message（工作区）
   │     ├─ field1 = "<name>"                string
   │     ├─ field2 = ARGB 颜色               varint，例如 0xFF8CABE4
   │     ├─ field3 = 最近使用时间            varint，µs
   │     ├─ field5 = share payload           message { field4: base64 doc id }
   │     ├─ field6 = 共享标记                varint 0/1
   │     ├─ field8 = 保留                    varint
   │     ├─ field9 = "<emoji>"               string，UTF-8，图标字段
   │     └─ field10 = 保留                   varint
   └─ field3 = { field1: 0 }                 message，固定标记
```

区分实体类型：

- `specifics.field4` 存在 → 工作区
- `specifics.field5` 存在 → 标签页（内含父工作区 id、url、标题、favicon）

已实测的 emoji 值：`📁` = `F0 9F 93 81`（U+1F4C1，UTF-8 四字节）。
未发现专门的“默认图标 ID”；回退由**字段缺失**触发。字段存在但为空串的变体本机没有样本，
属于【可测】而非【事实】。

适配器写入时保留外层 field1 / field3 以及 details 内所有其他字段，只增删 `details.field9`，
并重算两级长度前缀。写入不是文本替换，不能直接用编辑器改 `.ldb`。
