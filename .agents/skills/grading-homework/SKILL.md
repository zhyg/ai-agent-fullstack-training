---
name: grading-homework
description: 获取极客时间训练营某周作业提交列表，并按 hw-guide 中本周评分标准逐份批改、归档到 homework 本周目录。Use when asked to 获取作业列表、批改作业、批改新获取的作业列表, or given a week and article ID.
---

# 批改训练营作业

用户每次提供**周次**和 **article ID**（如 `week02` + `1025885`）。缺任一项先问，不要猜。

## 1. 获取提交列表

1. 需要 `GEEKBANG_COOKIE`（个人 Secrets）。脚本报缺 Cookie 时，先运行 `amp orb restart-processes` 刷新环境再重试；仍缺少就请用户配置，不要让用户把 Cookie 发到对话里。
2. 运行：

   ```bash
   python .agents/skills/grading-homework/scripts/save_list.py --week week02 --article-id 1025885
   ```

   脚本用 `scripts/get_homework_user_list.py` 按默认 `status=0` 逐页取到空页，另存为 `homework/<周>/homework-list<NN>-pending-<时间戳>.{json,md}`。**已有列表一律不改**，只新增快照。`status=0` 返回全部记录，不是待批改清单。记录里的 `status`：1 已提交，2 批改后提交，8 已批改。1 和 2 都要批改；8 不重复批改。
3. 向用户报告记录数，以带“学员 | 学号 | 记录号”的表格列出。

## 2. 准备批改

- 评分标准：`hw-guide/<周>/` 下的 `第X周作业评分标准.md`，以及同目录的题目和原始附件（如 `hw2/` 里的原始测试）。反馈模板：`hw-guide/学员作业反馈报告模板与要求.md`。找不到本周标准就停下问用户。
- 先完整读标准和模板，记下各评分项、子项分值和判分口径。
- 创建汇总 artifact（学员、学号、记录号、状态），之后随结果更新。

## 3. 分发独立批改

每份提交用 `create_thread` 新开一个 orb 线程（`executor: orb`，沿用当前模式），**同时最多 5 个**；有线程结束再补新的。用 `wait_for_threads` 等待，不轮询。

给每个线程的提示需包含：

- 学员、学号、平台记录号、提交原文中的仓库链接（含子目录、指定提交）。
- 必须在新 orb 中实际 `git clone` 学员仓库，基于学员代码批改；不改学员业务代码和可信原始测试断言。
- 课程仓库当前分支名及提交号，标准、模板、原始附件的路径。
- 严格按本周标准逐项计分，同根因不重复扣分，等级只按总分；记录提交号、环境版本、实际导入路径、命令与退出码；区分“已确认缺陷”“未执行/被接口阻断”“未验证”。
- 已定下的同类扣分口径（见下方“统一尺度”）。
- 需要真实大模型时只用 DeepSeek 官方接口，`DEEPSEEK_API_KEY` 在个人 Secrets；离线可验收的不调用模型。
- 不建子线程、不提交推送、不写课程仓库的 `homework/`。
- 交付三件到**它自己** orb 的 `.amp/in/week-grading/`：
  `<学号>-<记录号>-feedback.md`（按模板的学员反馈）、`<学号>-<记录号>-evaluation.md`（逐项评分与最小复现）、`<学号>-<记录号>-evidence.tar.gz`（日志、补测脚本、源码快照、可信原测；不含密钥/venv/依赖目录）。不要上传到主线程。
- 最终答复给出总分、等级、验收结论、原测结果、扣分证据和三件文件路径。

线程报完成后，用 `amp.download_thread_file` 把三件下载到本 orb 的 `.amp/in/orb-backup/grading/`，文件名保持 `<学号>-<记录号>-*`。线程因模型额度等错误中断时，`read_thread` 查看进度，再用 `send_thread_message` 让它从已有状态继续，不要重开重复评测。

## 4. 复核与统一尺度

- 逐份读反馈和评分附件，抽查测试日志。按本周评分表逐项加总，核对合计与反馈里的分数一致，再核等级分段和反馈各节不超过 500 字。评分附件改完后重新加总，不要沿用改前的总分。
- 同一类问题在不同学员间必须同样扣分。发现不一致，用 `send_thread_message` 让对应线程修订三件（包内报告和校验清单同步）后重新下载。把定下的口径写进汇总 artifact，并加入后续线程的提示。
- 学员提交与题目明显不符（如误交其他项目）时给暂评分并注明待补证，提醒用户核实链接，不推断下游业务全部错误。

## 5. 归档（不覆盖已有记录）

```bash
python .agents/skills/grading-homework/scripts/archive.py --week week02 --list homework/week02/homework-list02-pending-<时间戳>.json
```

规则（同一学员可能多次提交）：

- 该学号本周还没有 `<学号>.md`：存为 `homework/<周>/<学号>.md`，附件 `attachments/<学号>.md`、`attachments/<学号>-evidence.tar.gz`。
- 已有 `<学号>.md`：存为 `<学号>-submission<记录号>.md`，附件同名加 `-submission<记录号>`。
- 反馈首行写 `<!-- submission:<记录号> -->`，已归档的记录号自动跳过；所有写入独占创建，目标存在即报错，从不修改已有文件。

归档后运行 `git status --short` 和 `git diff --name-only`：应只有新增文件，`git diff` 为空。

## 6. 更新到平台

用户明确要求把批改记录更新到系统时，加载 `updating-homework-corrections` 并按其流程执行。

## 7. 报告

- 表格列出学员、**学号**、记录号、分数、等级、验收结论，并链接到各自 `homework/<周>/` 下的反馈文件。
- 说明暂评、需用户核实的事项，以及哪些未验证。
- **不自动提交推送**。用户说“提交并推送”时，只暂存本次新增文件，`git diff --cached --check` 通过后提交、推送到当前分支，并订阅该提交的 CI。
