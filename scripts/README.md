# 获取作业用户列表

在仓库根目录执行：

```bash
cp scripts/.env.example .env
# 编辑 .env，填写有效的 GEEKBANG_COOKIE。
uv run scripts/get_homework_user_list.py --article-id 1025885
```

脚本使用 Python 3.10+，`uv run` 会自动安装 `python-dotenv`。也可以自行安装
`python-dotenv>=1,<2` 后用 `python scripts/get_homework_user_list.py ...` 运行。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--article-id` / `--article_id` | 无，必填 | 文章 ID，正整数 |
| `--class-id` / `--class_id` | `899` | 班级 ID，正整数 |
| `--size` | `200` | 每页数量，正整数 |
| `--page` | `1` | 页码，正整数 |
| `--status` | `0` | 作业状态，沿用原请求 |

例如指定班级、每页数量和页码：

```bash
uv run scripts/get_homework_user_list.py --article-id 1025885 --class-id 899 --size 50 --page 2
```

脚本始终读取仓库根目录 `.env`，不依赖执行时的工作目录；已有环境变量优先。
`.env` 只需配置 `GEEKBANG_COOKIE`，模板见 `.env.example`。
接口地址、Origin、班级 SKU（`101178602`）和 User-Agent 固定在脚本中。
切换班级时，请同时确认脚本中的班级 SKU 与目标班级匹配。
Referer 根据班级、文章 ID 和 SKU 自动生成，请求 ID 每次自动生成。
浏览器专用的 `sec-*` 等请求头不需要复制。

脚本遍历响应中的 `data.list`，跳过 `status` 等于数字 `8` 的记录。
标准输出为格式化的 JSON 数组，每条记录仅保留
`id`、`content`、`status`、`name`、`student_no` 五个字段。缺失字段输出为 `null`，
空列表输出为 `[]`，可以用 `> users.json` 保存。
脚本只请求指定的一页，不自动翻页。HTTP、网络、JSON 解析失败或响应中的
`data.list` 不是对象列表时退出码为 1；参数错误或缺少 Cookie 时退出码为 2。
不要提交 `.env` 或分享 Cookie；`.env` 已加入 Git 忽略规则。

## 更新批改记录

先预览，确认无误后再提交：

```bash
uv run scripts/update_homework_correct.py --week week02 --article-id 1025885
uv run scripts/update_homework_correct.py --week week02 --article-id 1025885 --student-no G20261786020108 --apply
```

脚本读取 `homework/<周>/<学号>.md`。这份文件首行没有记录号、且该学号只有一份带记录号的 `*-submission*` 反馈时，改用那一份，不改已归档的旧文件。有多份时不猜测，仍按缺少记录号退出。
反馈须含 `作业等级：优秀（87分）` 这种等级和分数，以及“作业优点”“作业不足”“改进方案”三个 Markdown 列表。分数可以是整数或小数，如 `作业等级：优秀（81.64分）`。平台只提交等级。评语不得包含分数、扣分、得分或总分；等级行的分数只用于本地校验，不写入平台。
等级按 80 / 60 分段核验：优秀为 8，良好为 4，不及格为 1。`不及格（暂评0分，待补证100分）` 取暂评分数，0 分映射为不及格。未计分的反馈会跳过并记为失败。

提交编号必须取自反馈首行的 `<!-- submission:19468 -->`。任一反馈没有该编号时，脚本退出且不提交，并列出缺编号的文件。
三段列表分别用 `\n` 连接成一项，再按接口要求编码成 JSON 字符串数组。
提交前按反馈里的记录号向平台核实当前状态。`status` 为 8（已批改）的记录默认跳过，不提交，也不把这次跳过算作失败；需要覆盖时加 `--include-corrected`。平台上等级和评语已一致的记录同样跳过。省略 `--apply` 时不写平台。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--week` | 无，必填 | 周次目录，如 `week02` |
| `--article-id` / `--article_id` | 无，必填 | 文章 ID，正整数 |
| `--class-id` / `--class_id` | `899` | 班级 ID，正整数 |
| `--student-no` | 全部学号 | 只处理该学号，可重复 |
| `--apply` | 关闭 | 提交到平台；省略时只预览 |
| `--include-corrected` | 关闭 | 连已批改（status 8）的记录也提交；默认核实后跳过 |

Cookie、班级 SKU 和请求方式与获取列表脚本相同。列表获取失败、指定学号没有反馈，或任一记录无法匹配、提交失败、反馈无法解析时退出码为 1；参数错误时退出码为 2。未计分被跳过也算失败，退出码为 1。已批改记录的默认跳过不算失败。
