#!/usr/bin/env python3
"""用 scripts/get_homework_user_list.py 获取作业提交列表，另存为带时间戳的新快照。

用法：
  python save_list.py
  python save_list.py --article-id 1025885

省略 --article-id 时请求 article_id 为 null，一次取班级全部未批改作业，再按文章拆到对应周目录。
指定文章时只保存该周。已有列表一律不改；目标文件已存在时报错退出。
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

# 平台作业与本地评分目录的对照。没有评分标准的文章不写入 homework/。
WEEKS = {
    1009056: "week01",
    1025885: "week02",
    1025938: "week03",
    1028370: "week04",
}


def fetch(article_id: int | None, page: int) -> list[dict]:
    command = ["uv", "run", str(FETCH), "--page", str(page), "--size", "200"]
    if article_id is not None:
        command.extend(["--article-id", str(article_id)])
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"获取第 {page} 页失败（退出码 {result.returncode}）：{result.stderr.strip()}")
    return json.loads(result.stdout)


def write_snapshot(week: str, article_id: int, users: list[dict], counts: list[int], now: datetime) -> Path:
    out_dir = ROOT / "homework" / week
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"homework-list{week[4:]}-pending-{now:%Y%m%d-%H%M%S}"
    with base.with_suffix(".json").open("x") as stream:
        stream.write(json.dumps(users, ensure_ascii=False, indent=2) + "\n")

    lines = [
        f"# {week} 作业提交列表（status=0 查询快照）", "",
        f"来源：https://u.geekbang.org/review/lesson/899?article={article_id}&class_sku=101178602",
        f"采集时间：{now.isoformat(timespec='seconds')}",
        f"方法：`uv run scripts/get_homework_user_list.py --article-id {article_id} --page N`，逐页直到空页。",
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
    return base


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", help="只保留该周；省略时按文章拆分全部未批改作业")
    parser.add_argument("--article-id", type=int, help="只获取该文章；省略时获取全部作业")
    args = parser.parse_args()
    if args.week and not re.fullmatch(r"week\d{2}", args.week):
        sys.exit("--week 必须形如 week02")
    if args.article_id is not None and args.article_id not in WEEKS:
        sys.exit(f"文章 {args.article_id} 没有本地评分目录，不能保存为待批改快照")
    if args.week and args.article_id and WEEKS[args.article_id] != args.week:
        sys.exit(f"文章 {args.article_id} 属于 {WEEKS[args.article_id]}，与 --week {args.week} 不一致")

    users, counts, page = [], [], 1
    while True:
        batch = fetch(args.article_id, page)
        counts.append(len(batch))
        if not batch:
            break
        users.extend(batch)
        page += 1
    ids = [user["id"] for user in users]
    if len(ids) != len(set(ids)):
        sys.exit("记录 ID 重复，请检查分页结果")

    grouped: dict[int, list[dict]] = {}
    unknown: dict[int, int] = {}
    for user in users:
        article_id = user.get("article_id")
        if article_id in WEEKS and (args.week is None or WEEKS[article_id] == args.week):
            grouped.setdefault(article_id, []).append(user)
        else:
            unknown[article_id] = unknown.get(article_id, 0) + 1

    now = datetime.now(ZoneInfo("Asia/Singapore"))
    if not grouped:
        print(f"记录数 0；各页 {counts}")
    for article_id, records in grouped.items():
        # 指定文章时各页数量属于这次请求；全部作业是一次取回后再拆分。
        page_counts = counts if args.article_id is not None else [len(records)]
        base = write_snapshot(WEEKS[article_id], article_id, records, page_counts, now)
        print(base.with_suffix(".json").relative_to(ROOT))
        print(base.with_suffix(".md").relative_to(ROOT))
        print(f"{WEEKS[article_id]} 记录数 {len(records)}")
    if unknown:
        skipped = "，".join(f"{article_id}:{count}" for article_id, count in sorted(unknown.items(), key=lambda item: str(item[0])))
        print(f"未保存（无评分目录或与 --week 不符）：{skipped}")


if __name__ == "__main__":
    main()
