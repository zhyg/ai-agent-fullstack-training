#!/usr/bin/env python3
"""用 scripts/get_homework_user_list.py 获取作业提交列表，另存为带时间戳的新快照。

用法：python save_list.py --week week02 --article-id 1025885
输出：homework/<week>/homework-list<NN>-pending-<YYYYmmdd-HHMMSS>.{json,md}
已有列表一律不改；目标文件已存在时报错退出。
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[4]
FETCH = ROOT / "scripts/get_homework_user_list.py"


def fetch(article_id: int, page: int) -> list[dict]:
    result = subprocess.run(
        ["uv", "run", str(FETCH), "--article-id", str(article_id), "--page", str(page)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"获取第 {page} 页失败（退出码 {result.returncode}）：{result.stderr.strip()}")
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", required=True, help="周次目录，如 week02")
    parser.add_argument("--article-id", type=int, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"week\d{2}", args.week):
        sys.exit("--week 必须形如 week02")

    users, counts, page = [], [], 1
    while True:
        batch = fetch(args.article_id, page)
        counts.append(len(batch))
        if not batch:
            break
        users.extend(batch)
        page += 1
    ids = [u["id"] for u in users]
    if len(ids) != len(set(ids)):
        sys.exit("记录 ID 重复，请检查分页结果")

    now = datetime.now(ZoneInfo("Asia/Singapore"))
    out_dir = ROOT / "homework" / args.week
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"homework-list{args.week[4:]}-pending-{now:%Y%m%d-%H%M%S}"

    with base.with_suffix(".json").open("x") as stream:
        stream.write(json.dumps(users, ensure_ascii=False, indent=2) + "\n")

    lines = [
        f"# {args.week} 作业提交列表（status=0 查询快照）", "",
        f"来源：https://u.geekbang.org/review/lesson/899?article={args.article_id}&class_sku=101178602",
        f"采集时间：{now.isoformat(timespec='seconds')}",
        f"方法：`uv run scripts/get_homework_user_list.py --article-id {args.article_id} --page N`，逐页直到空页。",
        "范围：查询 status=0，平台返回全部记录。记录 status 只有 1 已提交、2 批改后已提交、8 已批改；脚本再排除 8，快照只留 1 和 2。",
        f"记录数：{len(users)}；各页数量：{counts}", "",
        "| 序号 | 学员 | 学号 | 记录 | 状态 | 链接 |", "|---:|---|---|---:|---:|---|",
    ]
    for index, user in enumerate(users, 1):
        urls = re.findall(r"https?://[^\s（）)]+", user["content"] or "")
        links = "；".join(f"[链接{i}]({url})" for i, url in enumerate(urls, 1)) or "无链接"
        name = (user["name"] or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {index} | {name} | {user['student_no']} | {user['id']} | {user['status']} | {links} |")
    lines += ["", "## 完整提交原文", ""]
    for index, user in enumerate(users, 1):
        lines += [f"### {index}. {user['name']}｜{user['student_no']}", "",
                  f"记录 ID：{user['id']}；状态：{user['status']}", "", user["content"] or "", ""]
    with base.with_suffix(".md").open("x") as stream:
        stream.write("\n".join(lines))

    print(base.with_suffix(".json").relative_to(ROOT))
    print(base.with_suffix(".md").relative_to(ROOT))
    print(f"记录数 {len(users)}；各页 {counts}")


if __name__ == "__main__":
    main()
