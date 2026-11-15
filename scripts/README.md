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
