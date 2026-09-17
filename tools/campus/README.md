# 独立合成校园运行环境（t1 / multi-feature）

这里只创建本轮专属本地实例。师生生成规模为 10000，实际 HTTP 冒烟仅 2 名账号；这不是万人参与或千人并发验收。既有机构代码来自 `38ce3f0`，未经完整商业验收；旧流水线仍为 `blocked-manual`，旧被阻止检查不重试。

## 环境与固定版本

宿主只需要 Docker Desktop 和能运行标准库控制器的 Python；宿主 Python 不参与后端依赖或业务验证。后端运行 Python 3.11.14 Linux；Node 22.19.0 以独立容器核实。MySQL **8.0.39**、Redis **7.2.5** 是明确的开发验证版本，不能把结果说成 MySQL 8.4 / Redis 7.4；Qdrant 1.15.4。镜像均用摘要固定，完整 Python 依赖见 `requirements.lock`。

`backend/requirements_fixed.txt` 改为引用唯一基础清单，消除 SQLAlchemy 2.0.25 / 2.0.35 分歧；实际锁定 2.0.35。现有课表路由导入 pandas，已补充遗漏的 pandas 2.2.3。无全局依赖安装、无前端构建验收、无本地嵌入模型安装。

CPU 上限合计 4 核；内存限制合计 3520 MiB（MySQL 1536、Redis 128、Qdrant 512、后端 1024、依赖心跳 worker 256、回环网关 64）。这只是 t1 数据及正向 HTTP 预算。Docker 总配额、主机及镜像实际 ID 记录到每次 identity.json；共享主机的其他项目保持运行。

## 从空环境运行

在当前源码根目录执行：

```powershell
python tools/campus/run.py build
python tools/campus/run.py start --profile small --port 18100
```

控制器输出随机 run_id，不输出密码、token、响应正文。小档成功后按输出 run_id 停止容器，保留卷，再创建另一个全量运行：

```powershell
python tools/campus/run.py stop --run <小档run_id>
python tools/campus/run.py start --profile full --port 18101
```

每次启动都创建新 MySQL/Redis/Qdrant/后端/worker/HTTP网关、新内部网络、专属入口网络、4 个新命名卷；不接受自定义数据库 URL、旧容器或已有 `.env`。唯一发布端口是网关上的 `127.0.0.1:18100–18119` 范围内 HTTP 端口。启动前通过实际 bind 同时检查监听冲突与系统保留端口。数据库、Redis、Qdrant 不发布宿主端口，容器私网使用其标准端口不等于访问宿主 3306/6379。Docker Desktop 不向宿主发布仅 internal 网络容器的端口，因此只有 nginx 1.27.1 回环网关同时连接入口网络和内部网络；后端及依赖仍只在内部网络，网关只反向代理固定的 backend 地址，没有通用转发功能。

所有资源都有 `org.campusperf.run=<run_id>` 和 `org.campusperf.purpose=synthetic-campus-only` 标签，名称前缀 `campusperf-<run_id>`。控制器每次维护前核对容器网络、项目、卷、标签、回环端口及资源上限。MySQL 数据库为 `campus_perf_<run_id>`，应用用户只获该新库权限。Redis 独立实例，缓存及心跳使用 `campus_perf:<run_id>` 前缀。Qdrant 命名空间预留 `campus_perf_<run_id>` / `_chunks`，实际知识集合由 t4 依模型维度创建；t1 不假称已建立知识索引。

随机数据库、JWT、合成登录凭据只经 stdin 交给新容器进程，不进入 Docker Config.Env、命令参数、文件、报告或版本库。后续受控维护命令在**已校验标签的本轮后端容器**中从存活 PID 1 继承凭据；它不会读取原工作区配置。停止后没有保存明文秘密供重启，默认重新创建独立 run；保留的卷不能自动采用新凭据写入。失败 run 保留资源供定位，不自动清理。

Docker 网络标记 internal，应用另设仅允许本轮服务地址的连接门禁，API key 为空，AI 配置关闭。没有执行公网连通性探针。心跳 worker 只检查真实 SQL/Redis 依赖，**不是**已验收的持久 AI 或知识索引 worker；业务 worker 实现属于后续任务。

## 数据与可复用契约

| 项目 | small | full |
| --- | ---: | ---: |
| 教学机构 / 平台系统机构 | 5 / 1 | 5 / 1 |
| 学生 / 教师 | 190 / 10 | 9500 / 500 |
| 机构管理员 / 平台管理员 | 5 / 1 | 5 / 1 |
| 班级 / 课程 | 5 / 10 | 250 / 500 |
| 课程成员关系 | 380 | 19000 |
| 作业 / 题目 | 40 / 400 | 2000 / 20000 |
| 已交记录 / 答案 | 1026 / 10260 | 51300 / 513000 |
| 有合成附件的提交 | 103 | 5130 |
| 可供截止场景选择的未交学生 | 152 | 7600 |

由于既有平台角色要求 `code=platform`，organizations 表总行数为 6；只将前 5 个计入教学机构。学生每人两门课，教师每人一门课，每班 38 人；两份历史作业全交，一份日常作业按全局学生位置 50% 已交，一份截止作业 20% 已交。生成算法和时间锚点固定为 20260917。容量场景需要自己设置实际截止时间；默认未来期限防止正常读取演示立即过期。

附件为明确 synthetic 的确定性小文本文件，尺寸按 20 文件循环：12×1 KiB、5×4 KiB、2×16 KiB、1×64 KiB。全量共 33,564,672 字节（约 32 MiB），小档 658,432 字节。每个文件记录大小、SHA-256，manifest 另有整组哈希。数据库磁盘预算 512 MiB 是估计，实际表大小须实测。

`campus_fixture.py` 提供 `iter_identity_records(profile)`、`iter_pending_deadline_targets(profile)`、`expected_table_manifest(profile, run_id)`、`verify_fixture(...)`。`campus_http.CampusClient` 强制回环 IP、许可端口和健康响应的 run_id，禁止重定向及环境代理；登录凭据和 token 仅内存保存。指标仅有随机 trace、去标识参与者哈希、路由模板、状态码、客户端时间和 `Server-Timing`。后端以服务器生成或校验的 `X-Campus-Trace` 关联。不能据种子行数增加参与者数。

```powershell
python tools/campus/run.py status --run <run_id>
python tools/campus/run.py exec --run <run_id> -- python campus_fixture.py verify --profile full --output /runtime/verify.json
python tools/campus/run.py exec --run <run_id> -- python campus_fixture.py seed --profile full --output /runtime/replay.json
python tools/campus/run.py exec --run <run_id> -- python campus_smoke.py
python tools/campus/run.py export --run <run_id>
```

在无业务表的空 schema 中初始化模型；遇到已有但缺少必要表的 schema 拒绝。首次全部业务行和 fixture 标识在一个 MySQL 事务内提交，MySQL 运行锁避免并发播种。重复 seed 只验证；同 run_id 不同 profile、内容或附件冲突均拒绝，不删除歧义记录或覆盖冲突文件。孤立但内容完全相同的确定性附件可在事务重试时复用。

严格校验比较每表有序内容哈希及 SQL 关系、不重复、每人课程数、每份题数、每份答案数、四阶段数量、角色和平台机构口径。密码随机盐不纳入可重现内容哈希，另验证本轮凭据哈希一致性；run_id 出现在附件引用中，所以跨 run 比较时需使用同一 run_id 重新生成预期，而非要求不同 run 的整个 manifest 相同。t2/t5 修改数据后应使用自己的预期变更核对；严格基线校验会正确报告内容已变更，不能跳过校验假称基线不变。

`.campus-runs/<run_id>/` 保存可导出的非秘密证据；生成数据、模型、卷及密钥不入 git。工具没有删除卷的命令。实际备份恢复、迁移升级、完整浏览器及容量验证属于 t6/t5，不属于本文件的 t1 通过范围。继承商业条款见同目录 `commercial-traceability.md`。
