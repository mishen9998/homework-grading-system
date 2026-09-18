---
name: multi-agent-doc-workflow
description: 多 Agent 文档开发流水线：把需求文档/PRD/规格说明或对话中的需求文本，经「计划 → 开发 → 多维测试 → 定向修复 → 任务验收 → 最终验收」的可恢复流水线交付为代码产物；支持按 depends_on 拓扑调度、并行多维测试、3 次修复预算、双日志审计与会话恢复。当用户给出需求文档、PRD、规格说明并要求实现/开发/落地，或明确要求多 Agent、子 Agent 工作流、任务拆解流水线时使用；即使用户只给一段纯文本需求也应触发。
---

# 多 Agent 文档开发工作流（你是主调度 Agent）

把「输入 → 计划 → 任务开发 → 多维测试 → 定向修复 → 任务验收 → 最终验收」跑成可恢复、可审计的流水线。计划、开发、测试、最终验收全部委托给 Agent 工具创建的子 Agent，子 Agent 只通过**文件路径**与你通信。

```
用户 query ─► init 落盘规范化 ─► 计划 Agent ─► plan.md + tasks.json
                                    │
              pipeline plan-ready（校验 + 物化 + 任务数提醒）
                                    │
        开发循环：status 就绪任务 ─► 开发 Agent ─► result.md
              ─► 按维度并行测试 Agent ─► reports/<维度>.md
              ─► 全 pass → accepted → 下一个任务
              ─► 有 fail → 重入原开发修复 → 重入原测试验收（≤3 轮，超出 blocked）
                                    │
        全部 accepted ─► 最终验收 Agent ─► final-acceptance.md
              ├─ pass ─► completed ─► 结构化汇报
              └─ fail ─► 按责任 task_id 定向修复（共享 3 次预算）后重入重跑
```

## 角色边界（先读）

你只维护流程、状态、日志与调度：

- 不编写业务代码，不执行测试逻辑，不阅读实现文件与报告正文，不把大段子 Agent 输出粘进对话。
- 不自行决定需求怎么拆、测试用哪些维度——只归计划 Agent。
- 「不读内容」由脚本保证：一切元数据校验（路径存在/非空、报告首行 pass|fail、tasks.json 可解析且任务数一致）都由 `scripts/pipeline.py` 完成，你只解析它输出的一行 JSON。
- 修复与验收必须**重入**原子 Agent（用其 agentId 续跑），不新开无上下文 Agent；验收轮重跑该维度完整检查项，失败点对照只是附加要求。
- 全部任务 accepted ≠ 完成：必须经最终验收 Agent 对照用户原始需求做端到端验收。
- 计划标注 `need-user-input=true`（不可逆损失风险）时必须停下问用户；执行中的平台门禁或缺失授权也不能越过。任务数超阈值只**提醒**用户，提醒后继续。

## 脚本契约

`{SKILL}` 指本 skill 的基目录（加载本 skill 时系统会给出）。所有校验、状态变更、日志一律通过它完成：

```bash
python "{SKILL}/scripts/pipeline.py" <子命令> --workspace ./pipeline-workspace ...
```

- stdout 恒为一行 JSON，不回显任何文件正文；成败看 exit code：0 成功 / 2 参数或输入错误 / 3 前置状态不满足 / 4 元数据校验失败 / 5 IO 异常。
- 连续执行有依赖的操作时，先确认上一条 exit code 为 0 且 JSON 的 `ok=true`，再推进状态或写成功日志；一组校验中任一失败就停止后续成功分支，不能预先拼接“已通过”日志。
- `session.json`、`log.md`、`log.jsonl`、`progress.md` 只能由该脚本写，禁止手改；双日志每轮自动双写。
- 子 Agent 不调用该脚本，也不写日志文件。

| 子命令 | 用途 |
|---|---|
| `init` | 初始化工作区。`--mode document --input <文档路径>` 或 `--mode text --text "<需求原文>"`（自动落盘 `input.md`）。幂等：已存在则拒绝。自动探测 git 仓库并启用 worktree 隔离（`--no-worktree` 可关闭） |
| `worktree` | git 隔离：`--action ensure`（dispatch 后创建/找回任务分支+worktree）/ `--action merge`（accepted 后合并入主分支，冲突自动 abort）/ `--action prune`（清理树，分支保留；`--all` 全清） |
| `status` | 只读全量状态 + `ready_tasks` + `suggested_next`；**每次调度决策前跑，恢复会话先跑这个** |
| `register` | 登记子 Agent：`--role plan\|dev\|test\|final-acceptance --agent-id <id>`，可加 `--task t1`；test 角色必加 `--dimension`；重入加 `--reused`，重建加 `--recreated` |
| `validate-meta` | 元数据校验：`--kind path\|report\|tasks-json`；report 返回从首行提取的 `verdict`；tasks-json 返回 `problems` 列表 |
| `log` | 追加双日志事件：`--type <类型> --message "..."` |
| `advance` | 任务状态机：`--event dispatch\|dev-done\|fix-done\|test-result\|reset-ready\|reopen\|block`（dev-done/fix-done/test-result 需 `--report`；test-result 需 `--dimension`） |
| `pipeline` | 流水线状态机：`--event plan-ready\|start-final\|final-pass\|final-fail\|block` |
| `report` | 生成最终汇报数据：任务表 markdown、汇总、日志统计 |
| `errors` | 收割本轮错误事件（validate-fail / advance-rejected / pipeline-rejected / blocked / recover / agent-recreated / worktree-merge-conflict），`--types` 可筛选；终态复盘的输入 |

任务级状态机（脚本强制流转，非法流转会被拒绝并记日志）：
`pending → ready → developing → testing → accepted`；任一维度 fail 进入 `fixing`（fix-done 回 testing），3 轮修复后仍 fail → `blocked`。

## 工作区布局

默认在当前项目根建 `pipeline-workspace/`（用户指定了位置就用用户的，init/所有命令的 `--workspace` 保持一致）：

```
pipeline-workspace/
  session.json        # 状态机落盘处（含 input_mode/input_path/strategy/agents 注册表/tasks/git_mode/run_id）
  input.md            # 仅 text 模式：用户需求原文
  progress.md         # 人可读进度（脚本自动刷新）
  log.md / log.jsonl  # 双日志：人读 + 机器读（脚本独家写入）
  plan/plan.md, plan/tasks.json
  tasks/<task-id>/result.md, fix-round-<n>.md, reports/<维度>.md
  final-acceptance.md
  worktrees/<task-id>/ # git 模式：各任务的隔离工作树（gitignore 自动登记；prune 后清空，分支保留）
```

## 调度流程

### 第 0 步：输入规范化与初始化

1. 识别输入模式：用户给了文档路径 → document；只给了需求描述 → text。
2. `pipeline-workspace/session.json` 已存在 → 跑 `status` 续跑既有会话，**不要 init**。
3. 否则 init：`--mode document --input <路径>`（脚本会校验可读性，失败会提示你回问用户，不要猜）或 `--mode text --text "<原文>"`（脚本落盘 `input.md`）。
4. document 模式下计划 Agent 的输入就是该文档路径；text 模式下是 `pipeline-workspace/input.md`。

### 第 1 步：计划

1. Read `references/plan-agent.md` 全文，替换 `{WORKSPACE}`、`{INPUT_PATH}` 为绝对路径。
2. `Agent(subagent_type="general-purpose", prompt=<替换后的全文>)`。
3. 从 spawn 结果记下 agent_id → `register --role plan --agent-id <id>`。
4. 子 Agent 最终消息应只有两个路径 + 一行 `strategy=... / task_count=...`。若带 `need-user-input=true` + 原因：向用户转述并停下等补充——这是唯一必须停下的点。
5. `validate-meta --kind tasks-json --path <tasks.json> --strategy <策略> --claimed-count <N>`。
6. `pipeline --event plan-ready --tasks <tasks.json> --strategy <策略>`（内部再校验一遍并物化任务）。输出 `task_count_warning` 非空时，先向用户原样转述提醒，然后按计划继续。

### 第 2 步：开发循环

反复跑 `status`，按 `suggested_next` 行事，直到它指示进入最终验收。对每个 `ready_tasks` 里的任务（互不依赖的任务可在同一条消息里并行发出多个 Agent 调用；有依赖的严格等 `ready`）：

1. `advance --task <id> --event dispatch`。
2. **git 仓库内（status 的 `git_mode=true`）**：`worktree --action ensure --task <id>` —— 为任务创建独立分支 `pipeline/<run_id>/<task-id>` 与 worktree 目录；非 git 仓库该命令返回 git_mode=false，直接跳过本步。把返回的 worktree 路径作为 `{WORKTREE}` 填入 dev 模板。
3. Read `references/dev-agent.md`，填 `{WORKSPACE}` `{TASK_ID}` `{TASK_TITLE}` `{ACCEPTANCE}` `{STRATEGY}`（及 git 模式下的 `{WORKTREE}`），spawn 开发 Agent，`register --role dev --task <id> --agent-id <id>`。
4. 它应回 `result.md` 路径 + 一行 `success|partial|failed` → `advance --event dev-done --report <路径>`（校验失败按异常恢复处理）。
5. Read `references/test-agent.md`，按该任务 `dimensions` **每维度一个**测试 Agent 并行 spawn（填 `{DIMENSION}` `{ARTIFACT_PATHS}` 等——git 模式下产物路径在 worktree 内），逐个 `register --role test --task <id> --dimension <维度> --agent-id <id>`。注意平台有并发上限（约 3 个并发子 Agent）：一次 spawn 超限会被直接拒绝（"user concurrency limit exceeded"），把多余的按批重发即可，任务状态不受影响。
   - 若提示的是驻留线程总量上限，已完成不一定代表线程已释放；先查看并复用现有 Agent，不反复新建或假定嵌套 Agent 有额外名额。
6. 各测试应回报告路径 + 一行 `pass|fail` → 逐个 `advance --event test-result --dimension <维度> --report <路径>`（verdict 由脚本从首行提取，你不需要读报告）。
   - 全维度 pass → 任务 `accepted`，`status` 会自动把就绪的下游任务升为 `ready`。**git 模式下紧接着 `worktree --action merge --task <id>`**：把任务分支按拓扑序合并入主分支，合并后的集成态就是下游任务和最终验收的基线。
     - 合并冲突 → 脚本会 abort 并保持主树干净。按提示走：`advance --event reopen`（占修复预算）→ `worktree ensure` 找回该任务树 → 重入原开发 Agent 在其 worktree 内合并主分支、解决冲突、提交并写 fix-round 文件 → 正常 `fix-done` → 原测试复验 → accepted → 重新 merge。
   - 某维度 fail → 任务 `fixing`，走修复闭环：
     a. `SendMessage(to=<原开发 agent_id>)`：附失败报告路径，要求最小必要修复并另写 `tasks/<id>/fix-round-<n>.md`（根因/改动/验证方式）；git 模式下改动仍发生在此任务的 worktree 内；
     b. 收到回复后 `advance --event fix-done --report <fix-round 路径>`；
     c. `SendMessage(to=<原测试 agent_id>)`：要求重跑该维度完整检查项并覆盖同名报告，逐条对照上轮失败点；
     d. 再 `test-result`。预算 3 次：第 3 轮验收仍 fail，脚本自动置 `blocked`，你把原因与报告路径告知用户。
     - `fix-done` 后状态可能仍保留上轮报告；先收齐、校验本轮全部维度的正式报告，再推进验收。旧 `pass` 不能替代本轮完整复验，未完成的维度不能据此合并。

single-shot 策略只有一个任务，流程完全相同——不要因为"只有一个任务"就跳过多维测试或修复闭环。

### 第 3 步：最终验收

1. `status` 显示全部 accepted（含用户确认接受的 blocked）→ `pipeline --event start-final`；有 blocked 任务且用户已确认接受时加 `--allow-blocked <id列表>`。
2. Read `references/final-acceptance-agent.md`，填 `{WORKSPACE}` `{INPUT_PATH}` `{PLAN_PATH}` `{REPORT_INDEX}`（各任务 result/reports 路径索引，可从 `status` 或 `report` 输出拼出），spawn，`register --role final-acceptance --agent-id <id>`。git 模式下最终验收的对象是**主树的集成态**（全部任务分支已按拓扑序合并），抽查运行也应在主树进行。
3. 它应回 `final-acceptance.md` 路径 + 一行 pass|fail：
   - pass → `pipeline --event final-pass --report <路径>` → completed。
   - fail → `pipeline --event final-fail --report <路径> --reopen <责任task_id列表>`（脚本按共享预算把责任任务拉回 fixing）；git 模式下先 `worktree --action ensure --task <id>` 从既有分支找回该任务的树，再走第 2 步修复闭环（改动仍在 worktree 内），完成后重复合并、**重入最终验收 Agent 重跑完整端到端**，不是只看变更点。
   - 无法定位责任任务或预算耗尽 → `pipeline --event block --reason "<原因>"` 转人工。
4. 到达终态（completed / blocked）后，先完成下述运行材料留存检查，再 `worktree --action prune --all` 清掉全部任务 worktree 目录；分支一律保留，作为每任务的审计与回滚痕迹。

**合并与清理的留存检查：** `worktree --action merge` 也会立即移除任务工作树，不只是终态 prune。运行控制文件、唯一 manifest、忽略文件中的证据和容器挂载可能不在提交里；开发和检查 Agent 须先将必要材料保存到任务工作树外并验证入口，主调度确认已提交源码、精确路径和仍在运行的进程归属。无法确认安全时保留工作树并记录清理延期，不能用“分支还在”推断未跟踪材料可恢复。

### 第 4 步：最终汇报

`report` 子命令取数据，按此结构输出（数据以 log.jsonl 为准）：

- 流水线结论：completed / blocked: manual + 原因
- 最终验收：verdict + final-acceptance.md 路径
- 任务表：task_id / status / 修复轮数 / 各维度报告路径（直接用 `table_markdown`）
- 遗留风险与备注（来自各报告的「新风险」字段，可摘要转述）

### 第 5 步：错误复盘与 skill 自改进

流水线到达终态（completed / blocked: manual）或被中止后，若本轮出现过错误，**基于错误完善 skill 本身**；零错误则跳过，不为改而改。

1. `errors` 子命令收割本轮全部错误事件（脚本输出每条的类型、时间、task_id、agent_id、消息摘要）。
2. 逐条归因，对号入座：
   - **契约/提示词不清晰**（子 Agent 违约，如报告首行格式错、漏写必需字段）→ 修改对应 `references/*.md` 模板：优先补**字面示例**，而不是加新规则。
   - **脚本校验缺口**（坏产物通过了校验，或合法产物被误杀）→ 调整 `scripts/pipeline.py` 的校验逻辑。
   - **平台约束**（并发上限、SendMessage 异步、编码、路径分隔符等）→ 在 SKILL.md 对应步骤补一句操作指引。
   - **流程正常拦截**（门禁按设计工作，如非法流转被拒）→ 评估「预防是否比纠正更便宜」；不是就记录后不动。
3. 应用改进后验证：改了脚本 → 在临时工作区跑一遍冒烟（init → status → validate-meta → errors）；改了模板 → 通读一遍占位符与契约是否自洽。
4. 在最终回复里向用户输出「错误 → 根因 → 改动」清单。

护栏（硬性）：

- **运行中绝不改 skill**：改进只发生在终态之后——流转规则一旦定稿不得临场绕过。
- **绝不修改当前运行的工作区**：那是审计现场，不可篡改。
- **改进必须可泛化**：不要把一次偶发事故固化成永久规则；能改模板不改脚本，能改提示词不加机制。
- **系统性问题不静默重构**：若错误指向设计缺陷（补丁解决不了），如实告知用户并给建议，由用户决策。
- **skill 目录不可写**（如从插件缓存运行）时，把改进建议完整汇报给用户，不直接改。

## 重入与异常恢复

- 重入一律先查 `status` 输出的 `agents` 注册表拿 agent_id，用 `SendMessage` 续跑并 `register --reused`。`SendMessage` 是后台异步的：发出后等其完成通知（或轮询其应写的产物文件）再推进状态机，不要立即 advance。
- 用户中断后恢复时，先核实原 Agent 的后台命令和运行实例；已有命令可能完成或仍在执行，不重复启动有副作用的操作。状态中的旧报告结论不能代替本轮完整复验，须等本轮所有维度的新报告完成并校验后再判定。
- SendMessage 失败（Agent 已不可用）→ 用同一模板重建并**注入历史文件路径**（原 result、失败报告），`register --recreated`。
- 上一条仅适用于普通失联。平台安全门禁中止不是普通超时：保留现场并转人工，不通过重命名、改写提示或更换 Agent/工具重试被阻止操作；正常的资源保全不得夹带继续验收。
- 命中 Agent 总数或并发上限时，不循环创建；先核对现有可用 Agent，复用或分批安排。工具不可用时保留任务状态与证据，不能跳过独立检查。
- 工具明确的安全拒绝不属于 Agent 失联，不走上述重建重试：不换 Agent、工具或改写请求绕过受阻操作；保留已有产物，将缺失验收标为未验证并报告阻塞，等待外部条件恢复或用户指示。
- 开发 Agent 无响应或返回非法路径 → `advance --event reset-ready`（任务回 ready），重入原开发 Agent，要求**覆盖更新**已有产物，不从头重写。
- 某维度测试 Agent 普通失败/超时 → 只重启该维度的测试 Agent，任务保持 testing，状态不动；平台门禁中止按上述例外转人工，不重试。
- 单任务卡死或用户中止 → `advance --event block --task <id> --reason` 或流水线级 `pipeline --event block --reason`。
- git 模式下 worktree 目录丢失（会话恢复、误删）→ `worktree --action ensure` 从既有分支自动找回；主树有未提交改动时 merge 会拒绝，请用户先 commit/stash。

## 子 Agent 提示词模板

`references/` 下四份模板，均为**自包含**正文（子 Agent 不加载本 skill，看不到本文件）：

- `references/plan-agent.md` —— 计划 Agent（可拆解性判定 → plan.md + tasks.json）
- `references/dev-agent.md` —— 开发 Agent（实现 + result.md / fix-round-<n>.md）
- `references/test-agent.md` —— 测试 Agent（单维度 + reports/<维度>.md 首行 pass|fail 契约）
- `references/final-acceptance-agent.md` —— 最终验收 Agent（对照原始需求端到端）

spawn 方法：Read 模板全文 → 替换占位符 → 作为 `Agent` 工具的 `prompt`（subagent_type 用 `general-purpose`）。ZCode 的 Agent 工具只接受 prompt 与 subagent_type，平台相关的身份/能力约束已并入模板正文；子 Agent 与你的全部通信就是它的最终消息，因此模板里把「只回路径 + 一行状态」写成了硬契约。

## 不变规则

1. 主 Agent 维护流程，子 Agent 决定质量；你只处理路径、状态、计数器、日志行。
2. 输入先规范化：文档路径直接用；普通文本必须先经 init 落盘，计划 Agent 永远读文件。
3. 拆解策略与测试维度只由计划 Agent 产出；不可拆就老实走 single-shot，不要制造伪任务。
4. 每条返回路径必经脚本元数据校验；校验失败 = 该子 Agent 本轮失败，不得带病继续。
5. 谁开发谁修、谁测试谁验收——都以重入实现；验收轮重跑完整检查项。
6. 修复最多 3 次（最终验收触发的定向修复共享同一预算），超限转 blocked: manual。
7. 缺信息默认带假设推进（假设清单在 plan.md），只有不可逆损失风险才回问用户。
8. 每轮状态变化自动落盘双日志；最终汇报以 log.jsonl 为准。
9. multi-feature 必须真正按 depends_on 拓扑调度（以 status 的 ready_tasks 为准），不是按列表顺序硬跑。
10. 状态以 session.json 为准，恢复会话先 `status`，不靠对话记忆。
11. 终态后做错误复盘（第 5 步）：错误驱动改进 skill 本身；改进只落在终态之后，运行中绝不改规则。
12. git 仓库内运行时，代码产物一律在各任务自己的 worktree 分支上开发与测试，按拓扑序合并入主分支，主树只承载流程元数据与集成态；非 git 仓库自动降级为直写项目目录，流程与状态机不变。
