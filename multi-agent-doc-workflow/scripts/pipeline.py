#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline.py —— 「多 Agent 文档开发工作流」的确定性助手脚本（主 Agent 专属）。

分工原则：Agent 负责判断，脚本负责机械。
  拆不拆、测哪些维度、质量好不好 —— 子 Agent 判断，脚本一律不管；
  状态机流转、依赖就绪、修复预算（3 次）、双日志双写、元数据级校验 —— 脚本保证，
  LLM 不得手改 session.json / log.md / log.jsonl / progress.md。

对主 Agent 的契约：
  1. stdout 恒为一行 JSON，不回显任何文件正文；成败看 exit code：
     0 成功 / 2 参数或输入错误 / 3 前置状态不满足 / 4 元数据校验失败 / 5 读写异常。
  2. 主 Agent 不 Read 计划、产物、报告的正文；要知道 pass|fail，
     用 validate-meta 或 advance（test-result / final-pass / final-fail），
     脚本替你读首行并回 verdict。
  3. 子 Agent 不调用本脚本：只按约定写文件、回路径、回一行状态。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

FIX_LIMIT = 3
DIMENSION_POOL = ["功能正确性", "边界与异常", "一致性与规范", "回归风险"]
EXTRA_DIMENSIONS = ["需求条款一致性"]
ALLOWED_DIMS = set(DIMENSION_POOL) | set(EXTRA_DIMENSIONS)

# 报告首行契约：可选 markdown 修饰后，第一个词必须是 pass 或 fail
VERDICT_RE = re.compile(r"^#{0,6}\s*[*_>\-\s]*(pass|fail)\b", re.IGNORECASE)

EXIT_OK, EXIT_USAGE, EXIT_STATE, EXIT_VALIDATE, EXIT_IO = 0, 2, 3, 4, 5


# ---------------------------------------------------------------- 基础工具

def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def one_line(text):
    return " ".join(str(text).split())


def out(payload, code=EXIT_OK):
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(code)


def fail(code, error, **extra):
    payload = {"ok": False, "error": error}
    payload.update(extra)
    out(payload, code)


def ws_paths(workspace):
    root = Path(workspace).expanduser().resolve()
    return {
        "root": root,
        "session": root / "session.json",
        "log_md": root / "log.md",
        "log_jsonl": root / "log.jsonl",
        "progress": root / "progress.md",
        "input": root / "input.md",
        "plan": root / "plan",
        "tasks": root / "tasks",
    }


def load_session(p):
    if not p["session"].is_file():
        fail(EXIT_STATE, f"工作区不存在或未初始化（找不到 {p['session']}），请先 init")
    try:
        return json.loads(p["session"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        fail(EXIT_IO, f"session.json 不可读或损坏：{e}")


def run_git(cwd, *args):
    """确定性执行 git 命令，返回 (returncode, stdout, stderr)。"""
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except OSError as e:
        return 127, "", str(e)


def detect_git(workspace_dir):
    """在 workspace_dir 下探测 git 仓库；返回 {"repo_root", "main_branch"} 或 None。"""
    code, top, _ = run_git(workspace_dir, "rev-parse", "--show-toplevel")
    if code != 0:
        return None
    code, branch, _ = run_git(workspace_dir, "rev-parse", "--abbrev-ref", "HEAD")
    main_branch = branch if code == 0 and branch and branch != "HEAD" else None
    return {"repo_root": str(Path(top).resolve()), "main_branch": main_branch}


def save_session(p, s):
    tmp = p["session"].with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p["session"])
    except OSError as e:
        fail(EXIT_IO, f"session.json 写入失败：{e}")


def line_count(path):
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def append_log(p, ev_type, message, task_id=None, agent_id=None, detail=None):
    """双写：log.jsonl 一行一个 JSON 事件；log.md 一行一条人读记录。"""
    seq = line_count(p["log_jsonl"]) + 1
    ev = {"seq": seq, "ts": now_iso(), "type": ev_type, "message": one_line(message)}
    if task_id:
        ev["task_id"] = task_id
    if agent_id:
        ev["agent_id"] = agent_id
    if detail:
        ev["detail"] = detail
    with open(p["log_jsonl"], "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    ctx = ""
    if task_id:
        ctx += f" · `{task_id}`"
    if agent_id:
        ctx += f" · agent `{agent_id}`"
    with open(p["log_md"], "a", encoding="utf-8") as f:
        f.write(f"- [{seq:04d}] `{ev['ts']}` **{ev_type}**{ctx} — {ev['message']}\n")
    return ev


def write_progress(p, s):
    lines = [
        "# 进度",
        "",
        f"- 流水线状态：{s['pipeline_state']}",
        f"- strategy：{s.get('strategy') or '（待计划）'}",
        f"- 输入：{s['input_mode']} → {s['input_path']}",
        f"- 更新时间：{now_iso()}",
        "",
    ]
    if s["tasks"]:
        lines += ["| 任务 | 状态 | 修复轮 | 依赖 |", "|---|---|---|---|"]
        for tid in s["task_order"]:
            t = s["tasks"][tid]
            deps = ",".join(t["depends_on"]) or "-"
            lines.append(f"| {tid} | {t['status']} | {t['fix_round']} | {deps} |")
    if s.get("final_acceptance"):
        fa = s["final_acceptance"]
        lines += ["", f"- 最终验收：{fa['verdict']}（{fa['report']}）"]
    if s["pipeline_state"].startswith("blocked"):
        lines += ["", f"> 已转人工：{s.get('blocked_reason', '')}"]
    try:
        p["progress"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        fail(EXIT_IO, f"progress.md 写入失败：{e}")


def require_task(s, tid):
    t = s["tasks"].get(tid)
    if t is None:
        fail(EXIT_USAGE, f"任务 {tid} 不存在；现有任务：{','.join(s['task_order']) or '（无）'}")
    return t


# ------------------------------------------------------- 元数据校验（不回显正文）

def path_meta(path):
    """存在 + 非空检查；成功时返回 (True, 文本内容)，失败返回 (False, 原因)。"""
    fp = Path(path)
    if not fp.is_file():
        return False, "路径不存在或不是文件"
    try:
        data = fp.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return False, f"不可读：{e}"
    if not data.strip():
        return False, "文件为空"
    return True, data


def report_verdict(data):
    """取报告首个非空行的 pass|fail；不符合契约返回 None。"""
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        m = VERDICT_RE.match(line)
        return m.group(1).lower() if m else None
    return None


def validate_report(path, expect=None):
    """报告级校验：存在、非空、首行 pass|fail（可选：必须等于 expect）。"""
    ok, data = path_meta(path)
    if not ok:
        append_err = f"报告校验失败：{data}"
        return None, None, data
    v = report_verdict(data)
    if v is None:
        return None, None, "报告首行必须是 pass 或 fail（裸词或 #/*/- 修饰均可）"
    if expect is not None and v != expect:
        return None, v, f"报告首行为 {v}，与期望 {expect} 不符"
    return str(Path(path).resolve()), v, None


def find_cycle(parsed, idset):
    indeg = {tid: 0 for tid in idset}
    adj = {tid: [] for tid in idset}
    for item in parsed:
        tid = item.get("id")
        for d in (item.get("depends_on") or []):
            if d in idset and d != tid:
                adj[d].append(tid)
                indeg[tid] += 1
    queue = [t for t, d in indeg.items() if d == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if seen == len(idset):
        return None
    return sorted(t for t, d in indeg.items() if d > 0)


def validate_tasks(parsed, strategy):
    """tasks.json 结构校验，返回 (问题列表, task_count)。"""
    problems = []
    if not isinstance(parsed, list) or not parsed:
        return ["tasks.json 顶层必须是非空任务数组"], 0
    ids = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            problems.append(f"第 {i} 项不是对象")
            continue
        tid = item.get("id")
        if not tid or not isinstance(tid, str):
            problems.append(f"第 {i} 项缺少字符串 id")
            continue
        ids.append(tid)
        for f in ("title", "goal"):
            if not str(item.get(f) or "").strip():
                problems.append(f"{tid}.{f} 不能为空")
        for f in ("acceptance", "test_dimensions"):
            v = item.get(f)
            if not isinstance(v, list) or not v:
                problems.append(f"{tid}.{f} 必须是非空数组")
        if item.get("status") != "pending":
            problems.append(f"{tid}.status 必须是 pending（计划态）")
        dims = item.get("test_dimensions") or []
        bad = [d for d in dims if not isinstance(d, str) or d not in ALLOWED_DIMS]
        if bad:
            problems.append(
                f"{tid}.test_dimensions 超出维度池：{bad}（允许：{DIMENSION_POOL} + {EXTRA_DIMENSIONS}）")
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup:
        problems.append(f"任务 id 重复：{dup}")
    idset = set(ids)
    for item in parsed:
        tid = item.get("id")
        deps = item.get("depends_on") or []
        if not isinstance(deps, list):
            problems.append(f"{tid}.depends_on 必须是数组")
            continue
        for d in deps:
            if d not in idset:
                problems.append(f"{tid}.depends_on 引用不存在的任务：{d}")
            elif d == tid:
                problems.append(f"{tid} 依赖自己")
    cycle = find_cycle(parsed, idset)
    if cycle:
        problems.append(f"depends_on 存在环，无法拓扑排序：{cycle}")
    count = len(parsed)
    if strategy == "single-shot":
        if count != 1:
            problems.append(f"single-shot 只允许 1 个任务，当前 {count}")
        else:
            dims = parsed[0].get("test_dimensions") or []
            if "需求条款一致性" not in dims:
                problems.append("single-shot 的 test_dimensions 必含「需求条款一致性」")
    elif strategy == "multi-feature" and count < 2:
        problems.append("multi-feature 至少 2 个任务；确实不可拆请改用 single-shot")
    return problems, count


# ------------------------------------------------------------- 状态机助手

def refresh_ready(s):
    """依赖全部 accepted 的 pending 任务晋升 ready（物化 prompt §7 的派生边）。"""
    accepted = {tid for tid, t in s["tasks"].items() if t["status"] == "accepted"}
    for tid in s["task_order"]:
        t = s["tasks"][tid]
        if t["status"] == "pending" and all(d in accepted for d in t["depends_on"]):
            t["status"] = "ready"


def demote_dependents(p, s, tid):
    """tid 离开 accepted（重开/阻塞）时，其已就绪的下游退回 pending。"""
    for other in s["task_order"]:
        ot = s["tasks"][other]
        if ot["status"] == "ready" and tid in ot["depends_on"]:
            ot["status"] = "pending"
            append_log(p, "demote", f"上游 {tid} 离开 accepted，{other} 由 ready 退回 pending", task_id=other)


def apply_reopen(p, s, tid):
    """最终验收定向修复 / 重开：受同一 3 次预算约束。返回 fixing 或 blocked。"""
    t = s["tasks"][tid]
    if t["fix_round"] >= FIX_LIMIT:
        t["status"] = "blocked"
        t["blocked_reason"] = f"最终验收定向修复预算（{FIX_LIMIT} 次）已用尽"
        append_log(p, "blocked", f"重开被拒：{t['blocked_reason']}", task_id=tid)
        demote_dependents(p, s, tid)
        return "blocked"
    t["fix_round"] += 1
    t["status"] = "fixing"
    append_log(p, "reopen", f"最终验收 fail，定向重开 → 第 {t['fix_round']} 轮修复（重入原开发/原测试）", task_id=tid)
    demote_dependents(p, s, tid)
    return "fixing"


def task_warning(s, count):
    if count > s["threshold"]:
        return (f"任务数 {count} 超过阈值 {s['threshold']}：请向用户转达——建议精简或调整输入文档/需求范围；"
                f"用户未调整则按计划继续。")
    return None


# ------------------------------------------------------------------ 子命令

def cmd_init(a):
    p = ws_paths(a.workspace)
    if p["session"].is_file():
        fail(EXIT_STATE, "工作区已存在（session.json 已有）。恢复会话请用 status，不要重复 init。",
             workspace=str(p["root"]))
    if a.mode == "document":
        if not a.input:
            fail(EXIT_USAGE, "document 模式必须提供 --input 文档路径")
        src = Path(a.input).expanduser()
        ok, data_or_err = path_meta(src)
        if not ok:
            fail(EXIT_USAGE, f"输入文档不可用：{data_or_err}。请询问用户提供正确路径，不要让计划 Agent 猜。",
                 input=str(src))
        input_path = str(src.resolve())
    else:
        if not a.text or not a.text.strip():
            fail(EXIT_USAGE, "text 模式必须提供 --text 需求文本")
        input_path = str(p["input"])
    for d in (p["root"], p["plan"], p["tasks"]):
        d.mkdir(parents=True, exist_ok=True)
    git = None if a.no_worktree else detect_git(p["root"])
    s = {
        "schema": 1,
        "created_at": now_iso(),
        "run_id": datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + os.urandom(2).hex(),
        "input_mode": a.mode,
        "input_path": input_path,
        "threshold": a.threshold,
        "strategy": None,
        "pipeline_state": "planning",
        "git_mode": bool(git),
        "repo_root": git["repo_root"] if git else None,
        "main_branch": git["main_branch"] if git else None,
        "agents": {},
        "tasks": {},
        "task_order": [],
        "final_acceptance": None,
        "blocked_reason": None,
    }
    if a.mode == "text":
        p["input"].write_text(a.text.strip() + "\n", encoding="utf-8")
    save_session(p, s)
    p["log_md"].write_text("# 调度日志（人读）\n", encoding="utf-8")
    p["log_jsonl"].write_text("", encoding="utf-8")
    write_progress(p, s)
    append_log(p, "init", f"工作区初始化：input_mode={a.mode}，input={input_path}，threshold={a.threshold}"
               + (f"，git_mode=on（repo={s['repo_root']}，branch={s['main_branch']}）" if git
                  else "，git_mode=off（非 git 仓库或 --no-worktree）"))
    out({"ok": True, "workspace": str(p["root"]), "input_mode": a.mode, "input_path": input_path,
         "threshold": a.threshold, "pipeline_state": "planning", "git_mode": s["git_mode"],
         "run_id": s["run_id"],
         **({"repo_root": s["repo_root"], "main_branch": s["main_branch"]} if git else {})})


def cmd_status(a):
    p = ws_paths(a.workspace)
    s = load_session(p)
    tasks = s["tasks"]
    ready = [tid for tid in s["task_order"] if tasks[tid]["status"] == "ready"]
    waiting, unrunnable = [], []
    for tid in s["task_order"]:
        t = tasks[tid]
        if t["status"] != "pending":
            continue
        unmet = [d for d in t["depends_on"] if tasks[d]["status"] != "accepted"]
        blocked_dep = [d for d in unmet if tasks[d]["status"] == "blocked"]
        if blocked_dep:
            unrunnable.append({"task": tid, "reason": f"依赖被 blocked：{','.join(blocked_dep)}"})
        elif unmet:
            waiting.append({"task": tid, "waiting_for": unmet})
    in_flight = [tid for tid in s["task_order"] if tasks[tid]["status"] in ("developing", "testing", "fixing")]
    all_settled = bool(tasks) and all(t["status"] in ("accepted", "blocked") for t in tasks.values())
    state = s["pipeline_state"]
    if state == "planning":
        suggested = "把输入路径交给计划 Agent；拿到 plan.md/tasks.json 后先 validate-meta，再 pipeline plan-ready"
    elif state == "final-accepting":
        suggested = "等待最终验收 Agent 返回 final-acceptance.md；validate-meta 后 pipeline final-pass | final-fail"
    elif state.startswith("blocked"):
        suggested = "流水线已转人工（blocked: manual），等待用户处理"
    elif state == "completed":
        suggested = "已完成；输出最终汇报（数据以 log.jsonl 为准，可用 report 生成）"
    elif all_settled:
        suggested = "全部任务 accepted → pipeline start-final 启动最终验收"
    elif ready:
        suggested = f"按就绪顺序调度开发：{','.join(ready)}"
    else:
        suggested = "无就绪任务：等待在制任务返回，或检查依赖图是否死锁"
    warning = task_warning(s, len(tasks))
    out({
        "ok": True,
        "pipeline_state": state,
        "strategy": s.get("strategy"),
        "input_mode": s["input_mode"],
        "input_path": s["input_path"],
        "threshold": s["threshold"],
        "git_mode": bool(s.get("git_mode")),
        "run_id": s.get("run_id"),
        "task_count": len(tasks),
        "tasks": [
            {
                "id": tid,
                "title": tasks[tid].get("title"),
                "goal": tasks[tid].get("goal"),
                "acceptance": tasks[tid]["acceptance"],
                "result": tasks[tid].get("result"),
                "status": tasks[tid]["status"],
                "fix_round": tasks[tid]["fix_round"],
                "depends_on": tasks[tid]["depends_on"],
                "dimensions": tasks[tid]["dimensions"],
                "branch": tasks[tid].get("branch"),
                "worktree": tasks[tid].get("worktree"),
                "merged": tasks[tid].get("merged", False),
                "reports": {d: r["verdict"] for d, r in tasks[tid]["reports"].items()},
                "assignee_agent_id": tasks[tid]["assignee_agent_id"],
                "test_agents": tasks[tid]["test_agents"],
                **({"blocked_reason": tasks[tid]["blocked_reason"]} if tasks[tid].get("blocked_reason") else {}),
            }
            for tid in s["task_order"]
        ],
        "ready_tasks": ready,
        "in_flight": in_flight,
        "waiting": waiting,
        "unrunnable": unrunnable,
        "agents": {role: [r["agent_id"] for r in recs] for role, recs in s["agents"].items()},
        "task_count_warning": warning,
        "suggested_next": suggested,
    })


def cmd_register(a):
    p = ws_paths(a.workspace)
    s = load_session(p)
    recs = s["agents"].setdefault(a.role, [])
    existing = next((r for r in recs if r["agent_id"] == a.agent_id), None)
    reused = existing is not None
    if existing:
        if a.task and a.task not in existing["task_ids"]:
            existing["task_ids"].append(a.task)
    else:
        recs.append({"agent_id": a.agent_id, "created_at": now_iso(),
                     "task_ids": [a.task] if a.task else []})
    if a.task:
        t = require_task(s, a.task)
        if a.role == "dev":
            t["assignee_agent_id"] = a.agent_id
        elif a.role == "test":
            if not a.dimension:
                fail(EXIT_USAGE, "test 角色注册必须提供 --dimension（一个测试 Agent 负责一个维度）")
            if a.dimension not in t["dimensions"]:
                fail(EXIT_USAGE, f"维度 {a.dimension} 不在任务 {a.task} 的 test_dimensions 中")
            t["test_agents"][a.dimension] = a.agent_id
    if a.reused:
        ev_type = "agent-reused"
    elif a.recreated:
        ev_type = "agent-recreated"
    else:
        ev_type = "agent-registered"
    append_log(p, ev_type, f"注册 {a.role} Agent：{a.agent_id}" + ("（重入既有 Agent）" if reused else ""),
               task_id=a.task, agent_id=a.agent_id)
    save_session(p, s)
    out({"ok": True, "role": a.role, "agent_id": a.agent_id, "task": a.task, "reused": reused,
         "event": ev_type})


def cmd_log(a):
    p = ws_paths(a.workspace)
    s = load_session(p)
    if a.task:
        require_task(s, a.task)
    detail = None
    if a.detail:
        try:
            detail = json.loads(a.detail)
        except json.JSONDecodeError as e:
            fail(EXIT_USAGE, f"--detail 不是合法 JSON：{e}")
    ev = append_log(p, a.type, a.message, task_id=a.task, agent_id=a.agent_id, detail=detail)
    out({"ok": True, "event": ev})


def cmd_validate_meta(a):
    problems = []
    verdict = None
    task_count = None
    if a.kind == "tasks-json":
        if not a.path:
            fail(EXIT_USAGE, "tasks-json 校验必须提供 --path")
        if not a.strategy:
            fail(EXIT_USAGE, "tasks-json 校验必须提供 --strategy（multi-feature | single-shot）")
        ok, data = path_meta(a.path)
        if not ok:
            problems.append(data)
        else:
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError as e:
                problems.append(f"tasks.json 不可解析：{e}")
            else:
                problems, task_count = validate_tasks(parsed, a.strategy)
                if a.claimed_count is not None and not problems and task_count != a.claimed_count:
                    problems.append(f"任务数不一致：tasks.json 有 {task_count} 个，计划 Agent 声称 {a.claimed_count}")
        ok_all = not problems
        out({"ok": ok_all, "kind": a.kind, "path": a.path, "task_count": task_count,
             "problems": problems}, EXIT_OK if ok_all else EXIT_VALIDATE)
    if a.kind not in ("path", "report"):
        fail(EXIT_USAGE, f"未知 --kind：{a.kind}")
    if not a.path:
        fail(EXIT_USAGE, "必须提供 --path")
    ok, data = path_meta(a.path)
    if not ok:
        problems.append(data)
    elif a.kind == "report":
        verdict = report_verdict(data)
        if verdict is None:
            problems.append("报告首行必须是 pass 或 fail（裸词或 #/*/- 修饰均可）")
    out({"ok": not problems, "kind": a.kind, "path": str(Path(a.path).resolve()),
         "verdict": verdict, "problems": problems}, EXIT_OK if not problems else EXIT_VALIDATE)


def cmd_advance(a):
    p = ws_paths(a.workspace)
    s = load_session(p)
    t = require_task(s, a.task)
    ev, st = a.event, t["status"]

    def rej(code, msg, **kw):
        append_log(p, "advance-rejected", f"{ev} 被拒绝：{one_line(msg)}", task_id=t["id"])
        payload = {"ok": False, "error": msg, "task": t["id"], "current_status": st, "event": ev}
        payload.update(kw)
        out(payload, code)

    if ev == "dispatch":
        if st != "ready":
            rej(EXIT_STATE, f"只有 ready 任务可调度，当前 {st}（依赖未满足的任务保持 pending）")
        t["status"] = "developing"
        append_log(p, "dispatch", "调度开发 Agent（重入注册表中的原开发 Agent）", task_id=t["id"],
                   agent_id=t["assignee_agent_id"])
    elif ev in ("dev-done", "fix-done"):
        if ev == "dev-done" and st != "developing":
            rej(EXIT_STATE, f"dev-done 要求当前 developing，当前 {st}")
        if ev == "fix-done" and st != "fixing":
            rej(EXIT_STATE, f"fix-done 要求当前 fixing，当前 {st}")
        if not a.report:
            rej(EXIT_USAGE, "必须提供 --report（result.md / fix-round-<n>.md 路径）")
        ok, data = path_meta(a.report)
        if not ok:
            append_log(p, "validate-fail", f"路径校验失败：{data}；按该子 Agent 本轮失败处理", task_id=t["id"])
            fail(EXIT_VALIDATE, f"返回路径校验失败：{data}", path=a.report)
        resolved = str(Path(a.report).resolve())
        if ev == "dev-done":
            t["result"] = resolved
            t["status"] = "testing"
            append_log(p, "dev-done", "开发返回，result.md 校验通过 → testing", task_id=t["id"])
        else:
            t.setdefault("fix_reports", {})[str(t["fix_round"])] = resolved
            t["status"] = "testing"
            append_log(p, "fix-done", f"第 {t['fix_round']} 轮修复返回 → testing（重入原测试 Agent 验收）",
                       task_id=t["id"])
    elif ev == "test-result":
        if st != "testing":
            rej(EXIT_STATE, f"test-result 要求当前 testing，当前 {st}")
        if not a.dimension:
            rej(EXIT_USAGE, "test-result 必须提供 --dimension")
        if a.dimension not in t["dimensions"]:
            rej(EXIT_USAGE, f"维度 {a.dimension} 不在任务 test_dimensions（{t['dimensions']}）中")
        if not a.report:
            rej(EXIT_USAGE, "test-result 必须提供 --report")
        resolved, verdict, err = validate_report(a.report)
        if err:
            append_log(p, "validate-fail", f"维度「{a.dimension}」报告校验失败：{one_line(err)}；重启该维度测试 Agent",
                       task_id=t["id"])
            fail(EXIT_VALIDATE, err, dimension=a.dimension, path=a.report)
        t["reports"][a.dimension] = {"path": resolved, "verdict": verdict}
        if verdict == "fail":
            if t["fix_round"] >= FIX_LIMIT:
                t["status"] = "blocked"
                t["blocked_reason"] = f"第 {FIX_LIMIT} 轮修复后维度「{a.dimension}」验收仍 fail"
                append_log(p, "blocked", t["blocked_reason"] + "；记录原因与相关报告路径，转人工",
                           task_id=t["id"])
                demote_dependents(p, s, t["id"])
            else:
                t["fix_round"] += 1
                t["status"] = "fixing"
                append_log(p, "test-result", f"「{a.dimension}」fail → 进入第 {t['fix_round']} 轮修复"
                             f"（重入原开发 Agent）", task_id=t["id"])
        else:
            unpassed = [d for d in t["dimensions"] if t["reports"].get(d, {}).get("verdict") != "pass"]
            if unpassed:
                append_log(p, "test-result", f"「{a.dimension}」pass；待验收维度：{','.join(unpassed)}",
                           task_id=t["id"])
            else:
                t["status"] = "accepted"
                append_log(p, "accepted", "全部维度 pass → accepted", task_id=t["id"])
    elif ev == "reset-ready":
        if st != "developing":
            rej(EXIT_STATE, f"reset-ready 用于 developing 异常回退，当前 {st}")
        t["status"] = "ready"
        append_log(p, "recover", "开发 Agent 无响应/返回非法 → 回退 ready（重入原开发 Agent，覆盖更新产物）",
                   task_id=t["id"])
    elif ev == "reopen":
        if st != "accepted":
            rej(EXIT_STATE, f"reopen 要求当前 accepted，当前 {st}")
        new_status = apply_reopen(p, s, t["id"])
    elif ev == "block":
        if st == "blocked":
            rej(EXIT_STATE, "任务已是 blocked")
        if not a.reason:
            rej(EXIT_USAGE, "block 必须提供 --reason")
        t["status"] = "blocked"
        t["blocked_reason"] = a.reason
        append_log(p, "blocked", f"任务转人工：{one_line(a.reason)}", task_id=t["id"])
        demote_dependents(p, s, t["id"])
    else:
        fail(EXIT_USAGE, f"未知事件：{ev}")

    refresh_ready(s)
    save_session(p, s)
    write_progress(p, s)
    result = {
        "ok": True,
        "task": t["id"],
        "status": t["status"],
        "fix_round": t["fix_round"],
        "reports": {d: r["verdict"] for d, r in t["reports"].items()},
    }
    if ev == "test-result" and verdict:
        result["verdict"] = verdict
    if ev == "reopen":
        result["status"] = new_status
    out(result)


def cmd_pipeline(a):
    p = ws_paths(a.workspace)
    s = load_session(p)
    state = s["pipeline_state"]
    ev = a.event

    def rej(code, msg, **kw):
        append_log(p, "pipeline-rejected", f"pipeline {ev} 被拒绝：{one_line(msg)}")
        payload = {"ok": False, "error": msg, "pipeline_state": state, "event": ev}
        payload.update(kw)
        out(payload, code)

    warning = None
    if ev == "plan-ready":
        if state != "planning":
            rej(EXIT_STATE, f"plan-ready 只能在 planning 阶段，当前 {state}")
        if not a.tasks or not a.strategy:
            rej(EXIT_USAGE, "plan-ready 必须提供 --tasks（tasks.json 路径）与 --strategy")
        ok, data = path_meta(a.tasks)
        if not ok:
            append_log(p, "validate-fail", f"tasks.json 校验失败：{data}")
            fail(EXIT_VALIDATE, data, path=a.tasks)
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            append_log(p, "validate-fail", f"tasks.json 不可解析：{e}")
            fail(EXIT_VALIDATE, f"tasks.json 不可解析：{e}", path=a.tasks)
        problems, count = validate_tasks(parsed, a.strategy)
        if problems:
            append_log(p, "validate-fail", f"tasks.json 结构校验失败：{'；'.join(problems[:5])}")
            fail(EXIT_VALIDATE, "tasks.json 结构校验失败", problems=problems)
        s["tasks"] = {}
        s["task_order"] = []
        for item in parsed:
            tid = item["id"]
            s["tasks"][tid] = {
                "id": tid,
                "title": item.get("title", ""),
                "goal": item.get("goal", ""),
                "depends_on": list(item.get("depends_on") or []),
                "dimensions": list(item.get("test_dimensions") or []),
                "acceptance": list(item.get("acceptance") or []),
                "status": "pending",
                "fix_round": 0,
                "branch": None,
                "worktree": None,
                "merged": False,
                "result": None,
                "fix_reports": {},
                "reports": {},
                "assignee_agent_id": None,
                "test_agents": {},
                "blocked_reason": None,
            }
            s["task_order"].append(tid)
        s["strategy"] = a.strategy
        s["pipeline_state"] = "building"
        refresh_ready(s)
        warning = task_warning(s, count)
        if warning:
            append_log(p, "task-count-warning", warning)
        append_log(p, "plan-ready", f"计划就绪：strategy={a.strategy}，任务 {count} 个 → building")
        save_session(p, s)
        write_progress(p, s)
        out({"ok": True, "pipeline_state": "building", "strategy": a.strategy,
             "task_count": count, "task_count_warning": warning,
             "ready_tasks": [tid for tid in s["task_order"] if s["tasks"][tid]["status"] == "ready"]})
    elif ev == "start-final":
        if state != "building":
            rej(EXIT_STATE, f"start-final 只能在 building 阶段，当前 {state}")
        if not s["tasks"]:
            rej(EXIT_STATE, "没有任何任务：先 plan-ready")
        unfinished = [tid for tid in s["task_order"] if s["tasks"][tid]["status"] not in ("accepted", "blocked")]
        if unfinished:
            rej(EXIT_STATE, f"存在未完结任务：{','.join(unfinished)}")
        blocked_ids = [tid for tid in s["task_order"] if s["tasks"][tid]["status"] == "blocked"]
        allowed = {x for x in (a.allow_blocked or "").split(",") if x}
        unconfirmed = [tid for tid in blocked_ids if tid not in allowed]
        if unconfirmed:
            rej(EXIT_STATE, f"存在 blocked 任务且未被用户确认接受：{','.join(unconfirmed)}"
                            f"（确认后用 --allow-blocked {','.join(blocked_ids)}）")
        s["pipeline_state"] = "final-accepting"
        append_log(p, "start-final", f"全部任务完结，启动最终验收 Agent（blocked 已确认：{blocked_ids or '无'}）")
        save_session(p, s)
        write_progress(p, s)
        out({"ok": True, "pipeline_state": "final-accepting"})
    elif ev in ("final-pass", "final-fail"):
        if state != "final-accepting":
            rej(EXIT_STATE, f"{ev} 只能在 final-accepting 阶段，当前 {state}")
        if not a.report:
            rej(EXIT_USAGE, f"{ev} 必须提供 --report（final-acceptance.md 路径）")
        expect = "pass" if ev == "final-pass" else "fail"
        resolved, verdict, err = validate_report(a.report, expect=expect)
        if err:
            append_log(p, "validate-fail", f"最终验收报告校验失败：{one_line(err)}")
            fail(EXIT_VALIDATE, err, path=a.report,
                 hint=("报告结论为 fail 时应使用 final-fail" if ev == "final-pass" and verdict == "fail"
                       else "报告结论为 pass 时应使用 final-pass" if verdict == "pass" else None))
        s["final_acceptance"] = {"report": resolved, "verdict": verdict}
        if ev == "final-pass":
            s["pipeline_state"] = "completed"
            append_log(p, "final-acceptance", "最终验收 pass → completed")
            save_session(p, s)
            write_progress(p, s)
            out({"ok": True, "pipeline_state": "completed", "verdict": verdict, "report": resolved})
        ids = [x for x in (a.reopen or "").split(",") if x]
        if not ids:
            rej(EXIT_USAGE, "final-fail 必须提供 --reopen（逗号分隔的责任 task_id 列表）")
        unknown = [x for x in ids if x not in s["tasks"]]
        if unknown:
            rej(EXIT_USAGE, f"--reopen 含未知任务：{','.join(unknown)}")
        reopened = {tid: apply_reopen(p, s, tid) for tid in ids}
        s["pipeline_state"] = "building"
        append_log(p, "final-acceptance", f"最终验收 fail → 定向修复 {reopened}，回到 building（共享 3 次预算）")
        save_session(p, s)
        write_progress(p, s)
        out({"ok": True, "pipeline_state": "building", "verdict": verdict, "report": resolved,
             "reopened": reopened})
    elif ev == "block":
        if state.startswith("blocked") or state == "completed":
            rej(EXIT_STATE, f"当前 {state}，无法转 blocked")
        if not a.reason:
            rej(EXIT_USAGE, "block 必须提供 --reason")
        s["pipeline_state"] = "blocked-manual"
        s["blocked_reason"] = a.reason
        append_log(p, "blocked", f"流水线转人工：{one_line(a.reason)}")
        save_session(p, s)
        write_progress(p, s)
        out({"ok": True, "pipeline_state": "blocked-manual"})
    else:
        fail(EXIT_USAGE, f"未知流水线事件：{ev}")


def cmd_report(a):
    p = ws_paths(a.workspace)
    s = load_session(p)
    tasks = s["tasks"]
    by_type = {}
    malformed = 0
    events = 0
    if p["log_jsonl"].is_file():
        for raw in p["log_jsonl"].read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            events += 1
            try:
                by_type[json.loads(raw).get("type", "?")] = by_type.get(json.loads(raw).get("type", "?"), 0) + 1
            except json.JSONDecodeError:
                malformed += 1
    rows = ["| 任务 | 状态 | 修复轮 | 依赖 | 维度报告 |", "|---|---|---|---|---|"]
    detail = []
    for tid in s["task_order"]:
        t = tasks[tid]
        rep = " ".join(f"{d}:{r['verdict']}" for d, r in t["reports"].items()) or "-"
        deps = ",".join(t["depends_on"]) or "-"
        rows.append(f"| {tid} | {t['status']} | {t['fix_round']} | {deps} | {rep} |")
        detail.append({
            "id": tid, "status": t["status"], "fix_round": t["fix_round"],
            "depends_on": t["depends_on"], "result": t["result"],
            "branch": t.get("branch"), "merged": t.get("merged", False),
            "reports": {d: r["path"] for d, r in t["reports"].items()},
            "fix_reports": t["fix_reports"],
            **({"blocked_reason": t["blocked_reason"]} if t.get("blocked_reason") else {}),
        })
    summary = {
        "total": len(tasks),
        "accepted": sum(1 for t in tasks.values() if t["status"] == "accepted"),
        "blocked": sum(1 for t in tasks.values() if t["status"] == "blocked"),
        "fix_rounds_total": sum(t["fix_round"] for t in tasks.values()),
    }
    out({
        "ok": True,
        "pipeline_state": s["pipeline_state"],
        "strategy": s.get("strategy"),
        "input": {"mode": s["input_mode"], "path": s["input_path"]},
        "final_acceptance": s.get("final_acceptance"),
        "summary": summary,
        "table_markdown": "\n".join(rows),
        "tasks": detail,
        "log": {"md": str(p["log_md"]), "jsonl": str(p["log_jsonl"]),
                "events": events, "by_type": by_type, "malformed": malformed},
    })


# ------------------------------------------------------------------ 入口

ERROR_EVENT_TYPES = ("validate-fail", "advance-rejected", "pipeline-rejected",
                     "blocked", "recover", "agent-recreated", "worktree-merge-conflict")


def cmd_errors(a):
    """收割错误事件——终态后 skill 复盘自改进的机械输入。"""
    p = ws_paths(a.workspace)
    load_session(p)
    types = [x for x in (a.types or "").split(",") if x] or list(ERROR_EVENT_TYPES)
    events = []
    by_type = {}
    if p["log_jsonl"].is_file():
        for raw in p["log_jsonl"].read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if ev.get("type") in types:
                events.append(ev)
                by_type[ev["type"]] = by_type.get(ev["type"], 0) + 1
    out({"ok": True, "total": len(events), "by_type": by_type,
         "types": types, "events": events})


def _ensure_gitignore(p, repo_root):
    """worktree 目录在仓库内时，确保被 .gitignore 忽略。返回 outside|already|updated。"""
    ws_rel = os.path.relpath(p["root"], repo_root)
    if ws_rel.startswith(".."):
        return "outside"
    code, _, _ = run_git(repo_root, "check-ignore", "-q",
                         str(p["root"] / "worktrees") + os.sep)
    if code == 0:
        return "already"
    entry = ws_rel.replace("\\", "/").rstrip("/") + "/worktrees/"
    gi = repo_root / ".gitignore"
    try:
        existing = gi.read_text(encoding="utf-8") if gi.is_file() else ""
        if entry in [l.strip() for l in existing.splitlines()]:
            return "already"
        with open(gi, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(entry + "\n")
    except OSError as e:
        fail(EXIT_IO, f".gitignore 写入失败：{e}")
    return "updated"


def _remove_worktree(p, s, t):
    """移除任务 worktree 目录（分支保留），返回是否实际移除。"""
    wpath = t.get("worktree")
    if not wpath or not Path(wpath).exists():
        t["worktree"] = None
        return False
    code, _, err = run_git(s["repo_root"], "worktree", "remove", wpath)
    if code != 0:
        code, _, err = run_git(s["repo_root"], "worktree", "remove", wpath, "--force")
    if code != 0:
        append_log(p, "worktree-prune", f"worktree 清理失败（保留现场）：{one_line(err)}",
                   task_id=t["id"])
        return False
    t["worktree"] = None
    append_log(p, "worktree-pruned", f"已移除 worktree（分支 {t['branch']} 保留）", task_id=t["id"])
    return True


def cmd_worktree(a):
    p = ws_paths(a.workspace)
    s = load_session(p)
    if not s.get("git_mode"):
        out({"ok": True, "git_mode": False, "action": a.action, "task": a.task,
             "note": "git 模式未启用（非 git 仓库或 init --no-worktree），worktree 为空操作，产物直接写在项目目录"})
    if a.action == "ensure":
        t = require_task(s, a.task)
        if t["status"] not in ("ready", "developing", "fixing"):
            fail(EXIT_STATE, f"ensure 要求任务处于 ready/developing/fixing，当前 {t['status']}")
        if not s.get("main_branch"):
            fail(EXIT_STATE, "主仓库处于 detached HEAD 或 unborn 分支，无法确定合并目标；"
                             "请先在主树创建/切换到工作分支并提交")
        repo_root = Path(s["repo_root"])
        if _ensure_gitignore(p, repo_root) == "updated":
            append_log(p, "gitignore-updated", "已把 worktrees/ 目录写入 .gitignore（隔离目录不可入库）")
        wpath = p["root"] / "worktrees" / t["id"]
        branch = t.get("branch")
        if branch:
            code, _, _ = run_git(s["repo_root"], "rev-parse", "--verify", branch)
            branch_exists = code == 0
            if not branch_exists:
                fail(EXIT_STATE, f"会话记录的分支 {branch} 在仓库中不存在，现场不一致，请人工检查")
        else:
            branch = f"pipeline/{s['run_id']}/{t['id']}"
            branch_exists = False
        if wpath.exists() and (wpath / ".git").exists():
            t["branch"], t["worktree"] = branch, str(wpath)
            save_session(p, s)
            out({"ok": True, "action": "ensure", "task": t["id"], "branch": branch,
                 "worktree": str(wpath), "recovered": False, "note": "worktree 已存在，复用"})
        if branch_exists:
            code, _, err = run_git(s["repo_root"], "worktree", "add", str(wpath), branch)
            ev_type, note = "worktree-recovered", f"从既有分支 {branch} 找回 worktree"
        else:
            code, _, err = run_git(s["repo_root"], "worktree", "add", "-b", branch,
                                   str(wpath), "HEAD")
            ev_type, note = "worktree-created", f"新建分支 {branch}（基于主树 HEAD）并挂载 worktree"
        if code != 0:
            fail(EXIT_IO, f"git worktree add 失败：{one_line(err)}", branch=branch, path=str(wpath))
        t["branch"], t["worktree"] = branch, str(wpath)
        save_session(p, s)
        append_log(p, ev_type, note + f"：{wpath}", task_id=t["id"])
        out({"ok": True, "action": "ensure", "task": t["id"], "branch": branch,
             "worktree": str(wpath), "recovered": branch_exists})
    if a.action == "merge":
        t = require_task(s, a.task)
        if t["status"] != "accepted":
            fail(EXIT_STATE, f"merge 要求任务已 accepted，当前 {t['status']}")
        if not t.get("branch"):
            fail(EXIT_STATE, "该任务没有分支（git 模式未启用或未 ensure）")
        if t.get("merged"):
            out({"ok": True, "action": "merge", "task": t["id"], "merged": True,
                 "note": "已合并过，幂等返回"})
        repo_root = Path(s["repo_root"])
        # 只检查已跟踪文件的未提交改动；未跟踪文件（含流水线审计目录）不阻塞合并，
        # merge 是否覆盖未跟踪文件由 git 自行裁决
        code, porcelain, _ = run_git(repo_root, "status", "--porcelain", "--untracked-files=no")
        if code != 0:
            fail(EXIT_IO, "git status 失败，无法确认主树状态")
        if porcelain.strip():
            fail(EXIT_STATE, "主工作树有未提交的已跟踪改动，拒绝合并；请用户先 commit 或 stash",
                 dirty=porcelain.splitlines()[:10])
        # 任务 worktree 内可能有未提交的产物：合并前机械提交（只动任务树，不碰主树）
        wpath = t.get("worktree")
        if wpath and Path(wpath).exists():
            code, wst, _ = run_git(wpath, "status", "--porcelain")
            if code == 0 and wst.strip():
                run_git(wpath, "add", "-A")
                msg = f"pipeline: {t['id']} deliverable"
                code, _, cerr = run_git(wpath, "commit", "-m", msg)
                if code != 0 and ("identify" in cerr.lower() or "who you are" in cerr.lower()):
                    code, _, cerr = run_git(wpath, "-c", "user.name=pipeline-script",
                                            "-c", "user.email=pipeline@local", "commit", "-m", msg)
                if code != 0:
                    fail(EXIT_IO, f"任务 worktree 内自动提交失败：{one_line(cerr)}", worktree=wpath)
                append_log(p, "worktree-autocommit",
                           f"合并前自动提交任务树内未提交产物（{one_line(wst.splitlines()[0])} 等）",
                           task_id=t["id"])
        code, _, err = run_git(repo_root, "merge", "--no-ff", "--no-edit", t["branch"])
        if code != 0:
            run_git(repo_root, "merge", "--abort")
            append_log(p, "worktree-merge-conflict",
                       f"分支 {t['branch']} 合并冲突，已 abort 保持主树干净；"
                       f"按 reopen → 重入原开发解决 → 复验 → 重新 merge 处理", task_id=t["id"])
            fail(EXIT_VALIDATE,
                 "合并冲突：主 Agent 应 advance --event reopen（占修复预算）→ worktree ensure 找回该任务树 → "
                 "重入原开发 Agent 在其 worktree 内合并主分支、解决冲突、提交并写 fix-round 文件 → "
                 "fix-done → test-result 复验 → 重新 merge",
                 branch=t["branch"])
        t["merged"] = True
        append_log(p, "worktree-merged", f"分支 {t['branch']} 已合并入 {s['main_branch']}",
                   task_id=t["id"])
        _remove_worktree(p, s, t)
        save_session(p, s)
        write_progress(p, s)
        out({"ok": True, "action": "merge", "task": t["id"], "branch": t["branch"], "merged": True})
    if a.action == "prune":
        if a.task:
            targets = [require_task(s, a.task)]
        elif a.all:
            targets = [s["tasks"][tid] for tid in s["task_order"]]
        else:
            fail(EXIT_USAGE, "prune 需要 --task <id> 或 --all")
        removed = []
        for t in targets:
            if _remove_worktree(p, s, t):
                removed.append(t["id"])
        run_git(s["repo_root"], "worktree", "prune")
        save_session(p, s)
        out({"ok": True, "action": "prune", "removed": removed,
             "branches_kept": sorted({t["branch"] for t in targets if t.get("branch")})})
    fail(EXIT_USAGE, f"未知 worktree 动作：{a.action}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="pipeline.py",
        description="多 Agent 文档开发工作流的确定性助手：状态机 / 元数据校验 / 双日志（详见模块 docstring）")
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="初始化工作区（幂等：已存在则拒绝）")
    sp.add_argument("--workspace", required=True)
    sp.add_argument("--mode", required=True, choices=["document", "text"])
    sp.add_argument("--input", help="document 模式：需求文档路径")
    sp.add_argument("--text", help="text 模式：需求原文（落盘为 input.md）")
    sp.add_argument("--threshold", type=int, default=6, help="任务数阈值，默认 6")
    sp.add_argument("--no-worktree", action="store_true",
                    help="即使处在 git 仓库内也不启用 worktree 隔离")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("status", help="只读：流水线/任务/Agent 全量状态 + 建议下一步（恢复会话先跑这个）")
    sp.add_argument("--workspace", required=True)
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("register", help="登记子 Agent ID（创建后立即调用；重入时加 --reused/--recreated）")
    sp.add_argument("--workspace", required=True)
    sp.add_argument("--role", required=True, choices=["plan", "dev", "test", "final-acceptance"])
    sp.add_argument("--agent-id", required=True)
    sp.add_argument("--task", help="关联任务 id")
    sp.add_argument("--dimension", help="test 角色必填：该 Agent 负责的维度")
    sp.add_argument("--reused", action="store_true", help="本次为重入（续跑）既有 Agent")
    sp.add_argument("--recreated", action="store_true", help="本次为同配置重建")
    sp.set_defaults(func=cmd_register)

    sp = sub.add_parser("validate-meta", help="元数据级校验：path / report / tasks-json（不回显正文）")
    sp.add_argument("--kind", required=True, choices=["path", "report", "tasks-json"])
    sp.add_argument("--path")
    sp.add_argument("--strategy", choices=["multi-feature", "single-shot"])
    sp.add_argument("--claimed-count", type=int, help="计划 Agent 声称的 task_count，用于一致性核对")
    sp.set_defaults(func=cmd_validate_meta)

    sp = sub.add_parser("log", help="追加一条双日志事件（主 Agent 独家写日志）")
    sp.add_argument("--workspace", required=True)
    sp.add_argument("--type", required=True, help="事件类型，如 dispatch / note / timeout")
    sp.add_argument("--message", required=True)
    sp.add_argument("--task")
    sp.add_argument("--agent-id")
    sp.add_argument("--detail", help='JSON 字符串，如 {"key":"value"}')
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("advance", help="任务状态机流转（内置元数据校验与 3 次修复预算）")
    sp.add_argument("--workspace", required=True)
    sp.add_argument("--task", required=True)
    sp.add_argument("--event", required=True,
                    choices=["dispatch", "dev-done", "fix-done", "test-result",
                             "reset-ready", "reopen", "block"])
    sp.add_argument("--report", help="result.md / fix-round-<n>.md / 维度报告路径")
    sp.add_argument("--dimension", help="test-result 必填")
    sp.add_argument("--reason", help="block 必填")
    sp.set_defaults(func=cmd_advance)

    sp = sub.add_parser("pipeline", help="流水线级状态机：plan-ready / start-final / final-pass / final-fail / block")
    sp.add_argument("--workspace", required=True)
    sp.add_argument("--event", required=True,
                    choices=["plan-ready", "start-final", "final-pass", "final-fail", "block"])
    sp.add_argument("--tasks", help="plan-ready：tasks.json 路径")
    sp.add_argument("--strategy", choices=["multi-feature", "single-shot"])
    sp.add_argument("--report", help="final-pass / final-fail：final-acceptance.md 路径")
    sp.add_argument("--reopen", help="final-fail：逗号分隔的责任 task_id")
    sp.add_argument("--allow-blocked", help="start-final：用户已确认接受的 blocked 任务")
    sp.add_argument("--reason", help="block 必填")
    sp.set_defaults(func=cmd_pipeline)

    sp = sub.add_parser("report", help="从 session.json + log.jsonl 生成结构化汇报数据")
    sp.add_argument("--workspace", required=True)
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("worktree",
                        help="git 隔离：ensure 创建/找回任务 worktree；merge 合并已验收分支；prune 清理树")
    sp.add_argument("--workspace", required=True)
    sp.add_argument("--action", required=True, choices=["ensure", "merge", "prune"])
    sp.add_argument("--task")
    sp.add_argument("--all", action="store_true", help="prune：清理全部任务 worktree（分支保留）")
    sp.set_defaults(func=cmd_worktree)

    sp = sub.add_parser("errors", help="收割错误事件（终态后 skill 复盘自改进的输入）")
    sp.add_argument("--workspace", required=True)
    sp.add_argument("--types", help="逗号分隔的事件类型；默认 validate-fail,advance-rejected,"
                                    "pipeline-rejected,blocked,recover,agent-recreated")
    sp.set_defaults(func=cmd_errors)

    return parser


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
