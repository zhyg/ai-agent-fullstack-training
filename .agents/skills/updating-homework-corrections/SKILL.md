---
name: updating-homework-corrections
description: 把已归档的学员反馈回填到极客时间作业批改系统。用户要求更新批改记录、回填评语、提交到平台、生成提交预览，或给出周次和学号要求上传批改时使用。不用于获取提交列表、批改作业或归档反馈。
---

# 回填批改记录

把 `homework/<周>/<学号>.md` 更新到 `https://u.geekbang.org/serv/v1/homework/correct`。脚本和字段规则在 [scripts/update_homework_correct.py](../../../scripts/update_homework_correct.py) 与 [scripts/README.md](../../../scripts/README.md)。缺周次或 article ID 时先问，不猜测。

## 流程

1. Cookie 为个人 Secret `GEEKBANG_COOKIE`。脚本报缺 Cookie 时，先运行 `amp orb restart-processes` 再重试；仍缺少就请用户配置，不让用户把 Cookie 发到对话里。
2. 先预览，不带 `--apply`：

   ```bash
   uv run scripts/update_homework_correct.py --week week02 --article-id 1025885
   ```

   只处理部分学员时重复 `--student-no`。向用户列出学号、记录号、等级和将提交或跳过的原因。用户要求看 body 时，说明该 body 由脚本从对应反馈生成，不另写一套编码。
3. 用户明确说提交后才加 `--apply`。提交前脚本按反馈里的记录号核实平台当前状态：`status` 为 8（已批改）的记录默认跳过，不提交。用户明确要求覆盖已批改记录时才加 `--include-corrected`。提交后用作业列表接口读回该记录，核对 `status`、`correct_level` 和 `correct_remark` 与本地反馈一致，再报告结果。
4. 不自动 `git commit` 或 `git push`。用户说“提交并推送”时，只暂存本次脚本和说明改动，`git diff --cached --check` 通过后提交、推送当前分支，并订阅该提交的 CI。

## 停下来问用户

- 反馈首行没有 `<!-- submission:记录号 -->`：脚本会整批退出且不提交。列出文件，不从平台列表补编号。
- 反馈没有可映射的分数，例如“待评（未计分）”：脚本跳过并退出。不把待补证的满分当成已得分。
- 用户没有明确要求提交：预览到此为止。
