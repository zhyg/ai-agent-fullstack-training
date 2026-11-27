# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv>=1,<2"]
# ///
"""获取极客时间作业用户列表；配置和运行方式见 scripts/README.md。"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--article-id",
        "--article_id",
        type=positive_int,
        help="文章 ID；省略时请求 article_id 为 null，返回班级全部作业",
    )
    parser.add_argument("--class-id", "--class_id", type=positive_int, default=899)
    parser.add_argument("--size", type=positive_int, default=200)
    parser.add_argument("--page", type=positive_int, default=1)
    # 这是查询参数，不是记录字段。0 表示不筛选；记录本身的 status 只有 1、2、8。
    parser.add_argument("--status", type=int, default=0, help="查询状态，默认 0 返回全部")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    cookie = os.getenv("GEEKBANG_COOKIE", "").strip()
    if not cookie:
        parser.error("请在仓库根目录 .env 中设置 GEEKBANG_COOKIE")

    origin = "https://u.geekbang.org"
    # 省略文章时走汇总入口；请求体里的 article_id 必须是 JSON null，不能省略该字段。
    query = urlencode({
        "article": args.article_id if args.article_id is not None else 0,
        "class_sku": "101178602",
    })
    payload = {
        "size": args.size,
        "page": args.page,
        "status": args.status,
        "class_id": args.class_id,
        "article_id": args.article_id,
    }
    request = Request(
        "https://u.geekbang.org/serv/v1/homework/get-user-list",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Cookie": cookie,
            "Origin": origin,
            "Referer": f"{origin}/review/lesson/{args.class_id}?{query}",
            "User-Agent": "Mozilla/5.0",
            "X-Geek-Req-Id": f"{uuid.uuid4().hex}@1@web",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        print(f"请求失败：HTTP {exc.code}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, ValueError) as exc:
        print(f"请求失败：{exc}", file=sys.stderr)
        return 1

    data = result.get("data") if isinstance(result, dict) else None
    records = data.get("list") if isinstance(data, dict) else None
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        print("响应格式错误：data.list 必须是对象列表", file=sys.stderr)
        return 1

    fields = ("id", "article_id", "content", "status", "name", "student_no")
    # 记录 status 只有三个取值：1 已提交，2 批改后已提交，8 已批改。
    # 查询参数 status=0 会返回全部记录，这里再排除已批改。
    users = [
        {field: item.get(field) for field in fields}
        for item in records
        if item.get("status") != 8
    ]
    print(json.dumps(users, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
