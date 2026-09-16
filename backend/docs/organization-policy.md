# 机构认证与下游接口契约

登录请求 `POST /api/auth/login` 必须提供 `organization_code`、`username`、`password`。
`role` 可选，只用于确认选择，不赋予权限。响应包含 `access_token`、`user`、
`organization` 和 `read_only`；`GET /api/auth/me` 返回相同身份与机构状态。
公共注册固定关闭，由平台创建机构及首位管理员，机构管理员开通其他账号。
平台管理员通过独立 CLI 创建，使用保留机构编码 `platform` 登录。

每个 API 请求在执行路由前验证数据库账号、组织状态，并将 JWT 的
`organization_id`、`role`、`token_version` 与数据库核对。历史无组织 JWT 不再接受。
身份变更、密码重置、停用与退出登录会撤销旧会话。`POST /api/auth/logout`
递增账号会话版本，撤销该账号现有登录凭证。不得在前端用组织 ID 切换上下文。

共用入口位于 `app.services.organization_context`：

- `current_user()`、`current_organization()`：返回已验证的数据库实体。
- `scoped_query(Model)`：仅查询当前机构，平台管理员不得调用此业务入口。
- `require_organization_id()`：仅在可信 HTTP 上下文生成新记录的机构默认值。
  离线脚本与 worker 必须显式传入 `organization_id`；没有隐式默认客户机构。
- `check_organization_policy(user, organization=None, write=False, external_ai=False,
  allow_platform=False)`：重复校验有效账号、机构与商业策略。worker 执行时重新读取
  User / Organization，重新调用，不得复用排队时缓存实体。
- `audit(action, target_type=None, target_id=None, details=None,
  organization_id=None, actor=None)`：审计与业务共用当前事务，由调用方统一提交。
  `details` 不记录密码、token、答案或附件内容。
- `session_claims(user)`：签发会话时使用，不用于服务端授权。
- `lock_current_identity(actor=None, roles=(), write=False, allow_platform=False)`：
  业务变更前以锁定读取刷新机构与账号，重验当前角色、状态、机构归属、会话版本和
  到期策略，持锁至业务/审计一并提交。已有目标机构先锁目标，再锁操作账号所属机构，
  最后锁操作账号；平台开通没有已有目标，直接从操作机构开始。机构管理、平台开通/
  续期/停用/额度变更以及退出共用此入口。延迟退出遇到已撤销会话返回 401，不写回
  旧会话版本；并发退出只允许尚有效的一次撤销及其审计。

`PolicyError` 响应为 `{"error": "可读说明", "code": "稳定错误码"}`。
401 错误码包含 `stale_session`、`account_inactive`、`authentication_required`；
403 包含 `organization_disabled`、`organization_expired`、`ai_not_authorized`、
`platform_business_denied`、`invalid_platform_identity`、`permission_denied`。普通角色仍需每个业务接口验证
课程成员、授课教师、父子对象及附件权限；这些对象规则在 t2 接入，不可仅依赖角色。

机构 `status=disabled` 拒绝业务访问；`expires_at` 到期且仍 active 时允许历史
GET/导出和 `POST /api/knowledge/assistant` 的 `mode=local`，拒绝业务写入和外部 AI。
本地检索接入方必须保持只读，不能借此白名单同步建索引或变更知识记录。
平台角色只可访问 `platform` 蓝图以及 `auth.me/logout`，无默认教学数据浏览权限。

权益字段为 `user_limit`、`storage_limit_bytes`、`ai_monthly_token_limit`、
`concurrent_task_limit`。`ai_enabled` 默认 false，由本机构管理员授权。
人员创建/导入通过组织行锁与总账号计数执行人数额度；包括停用账号，保留历史关系。
附件存储额度由 t2 的附件入口消费，月度 Token 和并发额度由 t3 持久网关消费。
现有 HTTP AI 接单入口已检查机构授权和有效期，t3 必须在执行时重新检查和结算。

所有业务实体均具有非空 `organization_id`。服务端创建新数据只使用认证上下文；
在 worker 中使用持久任务保存的机构归属，同时再验证业务对象父子链。
管理 API、班级关系及账号唯一性已直接执行机构范围检查；用户名和邮箱按机构唯一。

个人资料接口只允许 `name`、`email`、`phone`、`qq`；提交其他字段整体拒绝，
不能自行修改角色、用户名、组织、学号、工号、班级、学院、状态或会话版本。
