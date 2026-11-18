# week03 作业提交列表（status=0 查询快照）

来源：https://u.geekbang.org/review/lesson/899?article=1025938&class_sku=101178602
采集时间：2026-11-18T23:34:33+08:00
方法：`uv run scripts/get_homework_user_list.py --article-id 1025938 --page N`，逐页直到空页。
范围：查询 status=0，平台返回全部记录；脚本再排除 status=8（已批改），快照只留 1（已提交）和 2（批改后提交）。
记录数：2；各页数量：[2, 0]

| 序号 | 学员 | 学号 | 记录 | 状态 | 链接 |
|---:|---|---|---:|---:|---|
| 1 | Vita | G20210607020285 | 19398 | 1 | [链接1](https://gitee.com/vita__chaochao/smolagents/blob/master/%E4%BD%9C%E4%B8%9A.docx) |
| 2 | Kevin | G20200447020141 | 19380 | 1 | [链接1](https://gitee.com/huangke0802/agent-training/tree/master/homework/week03) |

## 完整提交原文

### 1. Vita｜G20210607020285

记录 ID：19398；状态：1

https://gitee.com/vita__chaochao/smolagents/blob/master/%E4%BD%9C%E4%B8%9A.docx

### 2. Kevin｜G20200447020141

记录 ID：19380；状态：1

https://gitee.com/huangke0802/agent-training/tree/master/homework/week03

1. 完整运行记录  agent-training/homework/week03/records/complete_run.json
                    agent-training/homework/week03/records/complete_run.md
  2. 审计记录      agent-training/homework/week03/records/audit.jsonl
                    agent-training/homework/week03/records/audit.json
                    agent-training/homework/week03/records/audit.md
  3. 恢复记录      agent-training/homework/week03/records/resume.json
                    agent-training/homework/week03/records/resume.md
  索引            agent-training/homework/week03/records/records.json
  完整运行：COMPLETED / COMPLETED；审计 65 条，哈希链 有效；恢复：COMPLETED / COMPLETED

python3 -m pytest -q
.................................                                          [100%]
33 passed in 6.36s
