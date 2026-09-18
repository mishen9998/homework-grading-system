# 机构和账号管理接口（t1）

这些接口复用 `organization_context` 的数据库身份、机构状态和 JWT 版本检查。所有业务机构均只有一个账号所属机构；请求中的 `organization_id`、`token_version` 等权限字段会被拒绝。路径中的其他机构对象返回 404。平台接口仅管理机构运行元数据，不提供教学内容读取权限。

## 平台开通与权益

只有 `platform_admin` 可访问 `/api/platform/*`。平台保留机构编码 `platform` 不出现在客户列表，也不能通过客户更新接口停用或修改。

| 方法与路径 | 请求和响应 |
| --- | --- |
| `GET /api/platform/organizations` | 分页客户列表；可传 `search`、`status=active/disabled`。响应 `organizations,total,page,per_page,has_next`。 |
| `POST /api/platform/organizations` | 创建机构并在同一事务开通首位活跃 `admin`。响应 201，包含 `organization` 与 `admin:{id,username,role}`。 |
| `GET /api/platform/organizations/{id}` | 响应 `organization` 元数据、四项额度及 `user_count`。 |
| `PUT /api/platform/organizations/{id}` | 修改 `name,status,expires_at,user_limit,storage_limit_bytes,ai_monthly_token_limit,concurrent_task_limit`；未传字段保持。 |

创建请求示例（密码仅为说明，实际由开通人员生成独立强密码）：

```json
{
  "code": "school-a",
  "name": "示例机构",
  "expires_at": "2030-01-01T00:00:00Z",
  "user_limit": 100,
  "storage_limit_bytes": 1073741824,
  "ai_monthly_token_limit": 100000,
  "concurrent_task_limit": 2,
  "admin": {
    "username": "org-admin",
    "email": "admin@example.test",
    "name": "机构管理员",
    "password": "Replace!UniquePassword42"
  }
}
```

`code` 规范为小写，2–80 位字母、数字、下划线或短横线，首位为字母或数字；创建后不可修改。创建必须传 `code/name/admin`，首位管理员必须传 `username/email/name/password`，不能指定角色或机构。默认机构为 active，500 人、1 GiB、每月 100000 Token、2 个并发任务、外部 AI 关闭；这些默认值由模型提供。

额度必须为非负整数，不接受布尔、小数或负数。首位管理员计入人数，零人数额度无法开通且事务不留下空机构；修改人数额度不能低于现有账号数。人数统计包含停用账号。存储、AI 和并发字段在 t1 只提供配置；实际用量账本和任务预留由 t2/t3 实现，接口不伪报实际用量。

`expires_at` 为 ISO 8601 日期时间或 null；有时区转换为 UTC，无时区按 UTC；转换后必须处于 MySQL DATETIME 的公元 1000–9999 年范围。null 明确表示无到期日，适用于经过平台确认的长期客户。到期保留历史读取、模板下载及本地检索权限，禁止业务写入；disabled 禁止机构业务访问。平台可读取到期/停用客户的元数据并续期/恢复。两类操作均不会删除客户数据。

平台不能修改 `ai_enabled`；该授权只由机构管理员设置。

## 机构人员

`/api/admin/users`、`/api/admin/import`、`/api/admin/statistics`、`/api/admin/template` 仅允许本机构 `admin`。平台管理员无权访问这些业务接口。

| 方法与路径 | 行为 |
| --- | --- |
| `GET /api/admin/users` | 默认分页（20 条，最多 100 条），支持 `search` 及 `role=student/teacher/admin`；返回 `users,total,page,per_page,has_next`。 |
| `POST /api/admin/users` | 创建本机构学生、教师或管理员；201。 |
| `GET /api/admin/users/{id}` | 返回本机构用户资料；其他机构为 404。 |
| `PUT /api/admin/users/{id}` | 更新白名单字段；角色、密码、活跃状态变化递增 `token_version`，旧登录凭证立即失效。 |
| `DELETE /api/admin/users/{id}` | 软停用，保留账号、关联教学记录和审计；返回明确提示与 `user`。重复停用保持幂等。 |
| `POST /api/admin/import` | multipart `file` 上传 `.xlsx`；最多 1000 个账号，整批成功或整批回滚。 |
| `GET /api/admin/template` | 只有表头的 `.xlsx` 模板，没有通用默认密码或预置真实资料。 |
| `GET /api/admin/statistics` | 本机构 `total_users/student_count/teacher_count/admin_count`。 |

创建必填 `username,email,password,role,name`。更新/创建允许字段为：`username,email,name,password,role,is_active,student_id,teacher_id,phone,qq,college,organization_class_id,class_name`。用户名和邮箱在机构内唯一，非空学号和工号也通过机构内校验；其他机构可以使用相同值。密码 12–256 字符，大小写字母、数字、符号中至少 3 类。

禁止 `platform_admin` 角色及机构 ID/Token 版本等未知字段。机构至少保留一位活跃管理员，最后一位不能降级、停用或 DELETE；停用管理员不算可用管理员。机构人员、额度及管理员保护通过先锁机构、再锁定读取当前账号实现，适配 MySQL REPEATABLE READ 下认证查询已经建立快照的情况。锁获得后再次核对操作账号状态与 JWT 版本。

Excel 列为：账号、密码、邮箱、角色、姓名、学号、工号、电话、QQ、班级、学院。前五列必需，其他可省略；未知/重复列和公式被拒绝，角色只接受 student/teacher/admin。学号、工号、电话等请用文本单元格保留前导零。任一行非法、重复或额度不足都回滚整个导入。成功返回 `success_count,error_count:0,errors:[]`；错误返回明确行号（可定位时），不会显示密码内容。

## 机构班级

`GET/POST /api/admin/classes` 和 `GET/PUT/DELETE /api/admin/classes/{id}` 仅本机构管理员可访问。列表使用相同分页协议；创建/更新接受 `{ "name": "班级名" }`，本机构班级名唯一。

用户通过 `organization_class_id` 关联本机构班级；null 清空。为兼容既有导入，`class_name` 只解析已经存在的本机构班级；不会自动创建或引用其他机构班级，同时指定 ID/名称时必须一致。班级改名同步本机构用户以及旧课程、课表字符串字段，其他机构同名班级不变。若有关联人员、课程或课表，DELETE 返回 409。普通班级名最多 100 字符；关联旧课表时改名不能超过 50 字符，因为旧课表字段仍为 VARCHAR(50)。

## 本机构权益与 AI 授权

- `GET /api/admin/organization`：本机构 admin/teacher/student 可读，返回 `organization`，包括当前状态、到期信息、四项额度、AI 授权和人数。
- `PUT /api/admin/organization`：仅 admin，且只接受 `{ "ai_enabled": true/false }`。禁止携带其他字段，拒绝布尔字符串；到期或停用机构不可写入。

所有成功管理变更与审计记录同事务提交。审计只包含动作、对象、额度变更或字段名称，不记录明文密码。主要错误码：400 `invalid_request/invalid_class`，401 `stale_session`，403 机构政策/角色错误，404 `not_found`，409 `user_limit_exceeded/last_active_admin/class_in_use/duplicate_user/data_conflict`。具体业务错误请读取响应 `code`，同时展示 `error`。

## 平台管理员初始化

先完成 t1 版本化数据库初始化/迁移，再在受控终端显式设置 `DATABASE_URL`、`SECRET_KEY`、`JWT_SECRET_KEY`，从 backend 目录运行 `python create_admin.py`。脚本使用 `create_app(ProductionConfig)`，不导入 run、不读取 `.env`，不回退到默认 SQLite。密码通过终端隐藏输入并确认，不接收命令行明文密码。

脚本创建独立 `platform_admin`，归入保留 `platform` 机构；业务机构原有同名管理员不会被升级或替换。平台机构含业务角色、被停用或存在到期时间时初始化中止。重复账号/邮箱或弱密码失败会回滚；不会自动建表或修改历史账号。

## 验证范围

`python -m unittest discover -s tests -p test_organization_admin.py -v` 在强制内存 SQLite、合成数据与关闭文件日志的配置运行；不读取 `.env`、真实数据库或附件，不调用外部模型。覆盖角色/机构边界、嵌套班级、软停用、旧凭证、最后管理员、额度、整批导入回滚、审计原子性、平台开通续期/停用、AI 授权及独立 bootstrap。SQLite 不证明 MySQL 行锁；真实 MySQL 并发额度验证由 t1 集成测试单独执行。
