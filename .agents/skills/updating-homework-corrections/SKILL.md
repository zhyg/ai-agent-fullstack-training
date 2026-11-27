---
name: updating-homework-corrections
description: 把已归档的学员反馈回填到极客时间作业批改系统。用户要求更新批改记录、回填评语、提交到平台、生成提交预览，或给出周次和学号要求上传批改时使用。一次批改覆盖多周时，按每周自己的快照分别回填。不用于获取提交列表、批改作业或归档反馈。
---

# 回填批改记录

按本次提交列表中的“学号＋记录号”选取已归档反馈，更新到 `https://u.geekbang.org/serv/v1/homework/correct`。脚本和字段规则在 [scripts/update_homework_correct.py](../../../scripts/update_homework_correct.py) 与 [scripts/README.md](../../../scripts/README.md)。回填按周执行：article ID 取自该周快照 md 的“来源”行，与周次的对照以 [save_list.py](../grading-homework/scripts/save_list.py) 的 `WEEKS` 为准。一次批改产生多周快照时，每周用自己的 `--week`、`--article-id` 和 `--list` 各跑一次，不把不同周混进同一个列表。快照缺失或无法确定属于哪周时先问，不猜测。

## 流程

1. Cookie 为个人 Secret `GEEKBANG_COOKIE`。脚本报缺 Cookie 时，先运行 `amp orb restart-processes` 再重试；仍缺少就请用户配置，不让用户把 Cookie 发到对话里。
2. 使用本次批改实际采用的提交快照 JSON（每项含 `student_no` 和 `id`），通过 `--list` 精确匹配反馈。沿用当前任务已确定的快照；有多份且无法确定本次范围时先问用户，不按文件时间、最大记录号或学号同名文件猜测，也不重新获取待批改列表替代本次快照。以下路径为示例，执行时换成实际快照。先预览，不带 `--apply`：

   ```bash
   uv run scripts/update_homework_correct.py --week week02 --article-id 1025885 --list homework/week02/homework-list02-pending-20261124-185535.json
   ```

   只处理部分学员时，在保留 `--list` 的同时重复 `--student-no`，进一步筛选本次列表。脚本根据反馈首行的记录号匹配学号同名及 `*-submission*` 文件，列表外的旧反馈不参与解析。向用户列出学号、记录号、等级和将提交或跳过的原因。用户要求看 body 时，说明该 body 由脚本从对应反馈生成，不另写一套编码。
3. 用户明确说提交后，沿用预览的同一列表及筛选参数，加 `--apply`：

   ```bash
   uv run scripts/update_homework_correct.py --week week02 --article-id 1025885 --list homework/week02/homework-list02-pending-20261124-185535.json --apply
   ```

   提交前脚本按反馈里的记录号核实平台当前状态：`status` 为 8（已批改）的记录默认跳过，不提交。用户明确要求覆盖已批改记录时才加 `--include-corrected`。提交后用作业列表接口读回本次列表及筛选范围内的记录，核对 `status`、`correct_level` 和 `correct_remark` 与本地反馈一致，再报告结果。
4. 提交、推送及交付文件范围遵循仓库 `AGENTS.md` 的约定。

## 停下来问用户

- 本次提交快照缺失或范围不明确：请用户确定列表或具体记录号；未确定前不退回不带 `--list` 的学号模式。
- 列表记录未匹配、匹配到多份反馈或列表重复：脚本会整批退出且不提交。列出具体学号、记录号和文件，请用户核实，不修改已归档反馈的首行标记来凑匹配。
- 选中反馈没有可映射的分数，例如“待评（未计分）”，或评语解析失败：整批退出。不把待补证的满分当成已得分。
- 用户没有明确要求提交：预览到此为止。
