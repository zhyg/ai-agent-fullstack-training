---
name: grading-homework
description: 获取极客时间训练营全部未批改作业，按文章对应的 hw-guide 评分标准逐份批改，并归档到 homework 对应周目录。Use when asked to 获取作业列表、批改作业、批改全部作业、批改新获取的作业列表, or given a week and article ID.
---

# 批改训练营作业

用户说“批改作业”且没有指定周次时，批改全部已有评分标准的未批改作业，不要再追问周次或 article ID。用户同时给出周次和 article ID 时，只按该文章取列表并批改那一周。只给了其中一项时先问另一项，不要用对照表补全。

文章与周次的对照只在 [scripts/save_list.py](scripts/save_list.py) 的 `WEEKS` 里维护，新增周次时只改那里。不在 `WEEKS` 里的文章（如作业五 `1033055`、作业六 `1035502`）本地没有评分标准：只向用户列出，不批改、不归档，也不要猜标准。

## 1. 获取提交列表

1. 需要 `GEEKBANG_COOKIE`（个人 Secrets）。脚本报缺 Cookie 时，先运行 `amp orb restart-processes` 刷新环境再重试；仍缺少就请用户配置，不要让用户把 Cookie 发到对话里。
2. 批改全部作业时运行 `python .agents/skills/grading-homework/scripts/save_list.py`；用户给了周次和 article ID 时加 `--week week02 --article-id 1025885`，只请求该文章。脚本按周另存新快照 `homework/<周>/homework-list<NN>-pending-<时间戳>.{json,md}`，从不改已有列表。快照里只有 status 1（已提交）和 2（批改后已提交），都要批改。
3. 向用户报告各周记录数。有待批改时，用一张表列出周次、学员、学号、记录号、状态；没有待批改时直接说明，不创建空批改线程。

## 2. 准备批改

- 评分标准：`hw-guide/<周>/` 下的 `第X周作业评分标准.md`，以及同目录的题目和原始附件。反馈模板：`hw-guide/学员作业反馈报告模板与要求.md`。
- 先完整读本批涉及的每一周标准和模板，记下各评分项、子项分值、判分口径和“扣分示例”一节里已执行的口径。各周口径分开，不把一周的扣分口径套到另一周。
- 对 status 2 的记录，找出该学号本周已归档的反馈（`homework/<周>/<学号>*.md`，首行记录号最大的一份）及其评测附件，写进子线程提示。
- 子线程从远程分支检出课程仓库。分发前确认当前分支已推送、`hw-guide/` 没有未推送的改动，否则子线程读到的是旧标准。
- 创建一份汇总 artifact，列出全部待批改记录（周次、学员、学号、记录号、状态），之后随结果更新。它只跟踪本批进度，口径的长期记录见第 4 节。

## 3. 分发独立批改

每份提交用 `create_thread` 新开一个 orb 线程（`executor: orb`，沿用当前模式），**同时最多 5 个**；有线程结束再补新的。用 `wait_for_threads` 等待，不轮询。提示按 [references/thread-brief.md](references/thread-brief.md) 填写，填入课程仓库当前分支和提交号。

线程报完成后，用 `amp.download_thread_file` 把三份文件下载到本 orb 的 `.amp/in/orb-backup/grading/`，文件名保持 `<学号>-<记录号>-*`。线程因模型额度等错误中断时，`read_thread` 查看进度，再用 `send_thread_message` 让它从已有状态继续，不要重开重复评测。

## 4. 复核与统一尺度

- 逐份读反馈和评分附件，抽查测试日志。按该提交所属周评分表的全部评分项逐项加总，核对合计与反馈里的分数一致，再核等级分段和反馈各节不超过 500 字。第一周是八项，其他周按各自评分表的项数核。评分附件改完后重新加总，不要沿用改前的总分。
- 同一周内，同一类问题在不同学员间必须同样扣分。发现不一致，用 `send_thread_message` 让对应线程修订三份文件（包内报告和校验清单同步）后重新下载。
- 定下的同类口径写进该周评分标准的“扣分示例”一节（问题＋处理，如“上游 4xx 被映射成 502｜只扣错误映射 1 分”），并加入同周后续线程的提示。下一批靠这一节延续尺度，所以不要只记在 artifact 里。
- 学员提交与题目明显不符（如误交其他项目）时给暂评分并注明待补证，提醒用户核实链接，不推断下游业务全部错误。

## 5. 归档（不覆盖已有记录）

每一周用该周自己的快照归档，不把不同周的记录放进同一个 `--list`：

```bash
python .agents/skills/grading-homework/scripts/archive.py --week week02 --list homework/week02/homework-list02-pending-<时间戳>.json
```

规则（同一学员可能多次提交）：

- 该学号本周还没有 `<学号>.md`：存为 `homework/<周>/<学号>.md`，附件 `attachments/<学号>.md`、`attachments/<学号>-evidence.tar.gz`。
- 已有 `<学号>.md`：存为 `<学号>-submission<记录号>.md`，附件同名加 `-submission<记录号>`。
- 反馈首行写 `<!-- submission:<记录号> -->`，已归档的记录号自动跳过；所有写入独占创建，目标存在即报错，从不修改已有文件。

归档后运行 `git status --short` 和 `git diff --name-only`：`homework/` 下应只有新增文件，`git diff` 只含第 4 节写回的评分标准。

## 6. 更新到平台

用户明确要求把批改记录更新到系统时，加载 `updating-homework-corrections` 并按其流程执行。

## 7. 报告

- 表格列出周次、学员、**学号**、记录号、分数、等级、验收结论，并链接到各自 `homework/<周>/` 下的反馈文件。没有待批改、或因缺少评分标准而跳过的文章，在表外说明。
- 说明暂评、需用户核实的事项、哪些未验证，以及本批写回评分标准的口径。
- 提交、推送及交付文件范围遵循仓库 `AGENTS.md` 的约定。
