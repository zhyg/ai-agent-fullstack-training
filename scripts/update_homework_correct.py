# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv>=1,<2"]
# ///
"""把本地学员反馈更新到极客时间作业批改接口。

从 homework/<周>/<学号>.md 读取等级和三段评语，POST 到
https://u.geekbang.org/serv/v1/homework/correct。
默认只预览；加 --apply 才提交。配置和运行方式见 scripts/README.md。
"""

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

ORIGIN = "https://u.geekbang.org"
CORRECT_URL = f"{ORIGIN}/serv/v1/homework/correct"
LIST_URL = f"{ORIGIN}/serv/v1/homework/get-user-list"
CLASS_SKU = "101178602"
LEVELS = {"优秀": 8, "良好": 4, "不及格": 1}
SECTIONS = ("作业优点", "作业不足", "改进方案")
STUDENT_NO = re.compile(r"^G\d+$")
SUBMISSION = re.compile(r"^<!-- submission:(\d+) -->\s*")
GRADE = re.compile(
    r"作业等级：\s*(优秀|良好|不及格)\s*[（(](?:[^）)]*?暂评)?\s*(\d+)\s*分"
)
LIST_ITEM = re.compile(r"^[-*]\s+(.*)$")


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return number


def section_bullets(text: str, title: str) -> list[str]:
    match = re.search(rf"^\*\*\d+\.\s*{title}\*\*\s*$", text, re.M)
    if not match:
        raise ValueError(f"缺少“{title}”")
    bullets = []
    for line in text[match.end():].splitlines():
        if re.match(r"^\*\*\d+\.", line):
            break
        item = LIST_ITEM.match(line)
        if item:
            bullets.append(item.group(1).strip())
        elif line.strip() and bullets:
            raise ValueError(f"“{title}”含非列表正文：{line.strip()}")
    if not bullets:
        raise ValueError(f"“{title}”没有列表项")
    return bullets


def parse_feedback(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    submission = SUBMISSION.match(text)
    grade = GRADE.search(text)
    if not grade:
        raise ValueError("等级必须是“优秀 / 良好 / 不及格（N分）”，未计分不能提交")
    level_name, score = grade.group(1), int(grade.group(2))
    expected = 8 if score >= 80 else 4 if score >= 60 else 1
    if LEVELS[level_name] != expected:
        raise ValueError(f"等级“{level_name}”与 {score} 分不一致")
    bullets = [section_bullets(text, title) for title in SECTIONS]
    return {
        "record_id": int(submission.group(1)) if submission else None,
        "level": LEVELS[level_name],
        "level_name": level_name,
        "score": score,
        "remark": json.dumps(["\n".join(f"- {item}" for item in group) for group in bullets], ensure_ascii=False),
        "counts": [len(group) for group in bullets],
    }


def load_feedbacks(week_dir: Path, selected: set[str]) -> tuple[dict[str, tuple[Path, dict]], list[str]]:
    found, skipped = {}, []
    for path in sorted(week_dir.glob("G*.md")):
        if not STUDENT_NO.fullmatch(path.stem) or (selected and path.stem not in selected):
            continue
        try:
            found[path.stem] = (path, parse_feedback(path))
        except ValueError as exc:
            skipped.append(f"{path.relative_to(week_dir.parent.parent)}：{exc}")
    return found, skipped


def request_json(cookie: str, url: str, payload: dict, referer: str) -> dict:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Cookie": cookie,
            "Origin": ORIGIN,
            "Referer": referer,
            "User-Agent": "Mozilla/5.0",
            "X-Geek-Req-Id": f"{uuid.uuid4().hex}@1@web",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(str(exc)) from exc
    if not isinstance(result, dict) or result.get("code") != 0:
        message = result.get("error") if isinstance(result, dict) else None
        raise RuntimeError(message or "接口返回失败")
    return result


def list_submissions(cookie: str, article_id: int, class_id: int) -> list[dict]:
    referer = f"{ORIGIN}/review/lesson/{class_id}?article={article_id}&class_sku={CLASS_SKU}"
    records, page = [], 1
    while True:
        result = request_json(cookie, LIST_URL, {
            "size": 50,
            "page": page,
            "status": 0,
            "class_id": class_id,
            "article_id": article_id,
        }, referer)
        batch = (result.get("data") or {}).get("list")
        if not isinstance(batch, list):
            raise RuntimeError("作业列表响应格式错误")
        if not batch:
            return records
        records.extend(batch)
        page += 1


def select_submission(records: list[dict], student_no: str, record_id: int) -> dict:
    chosen = [
        item for item in records
        if item.get("student_no") == student_no and item.get("id") == record_id
    ]
    if len(chosen) != 1:
        raise ValueError(f"平台上没有提交 {record_id}")
    return chosen[0]


def same_correction(record: dict, level: int, remark: str) -> bool:
    return record.get("correct_level") == level and record.get("correct_remark") == remark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", required=True, help="周次目录，如 week02")
    parser.add_argument("--article-id", "--article_id", type=positive_int, required=True)
    parser.add_argument("--class-id", "--class_id", type=positive_int, default=899)
    parser.add_argument("--student-no", action="append", default=[], help="只处理该学号，可重复")
    parser.add_argument("--apply", action="store_true", help="提交到平台；省略时只预览")
    args = parser.parse_args()
    if not re.fullmatch(r"week\d{2}", args.week):
        parser.error("--week 必须形如 week02")
    if any(not STUDENT_NO.fullmatch(item) for item in args.student_no):
        parser.error("--student-no 必须是学号，如 G20261786020108")

    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    cookie = os.getenv("GEEKBANG_COOKIE", "").strip().strip("'\"")
    if not cookie:
        parser.error("请在仓库根目录 .env 中设置 GEEKBANG_COOKIE")

    week_dir = root / "homework" / args.week
    if not week_dir.is_dir():
        parser.error(f"目录不存在：homework/{args.week}")
    selected = set(args.student_no)
    try:
        feedbacks, skipped = load_feedbacks(week_dir, selected)
    except RuntimeError as exc:
        print(f"准备失败：{exc}", file=sys.stderr)
        return 1

    unknown = sorted(selected - feedbacks.keys() - {item.split("/")[-1].split(".")[0] for item in skipped})
    if unknown:
        print(f"准备失败：没有这些学号的反馈：{', '.join(unknown)}", file=sys.stderr)
        return 1
    for item in skipped:
        print(f"SKIP {item}", file=sys.stderr)
    missing = [path for _, (path, feedback) in feedbacks.items() if feedback["record_id"] is None]
    if missing or skipped:
        if missing:
            print("缺少提交编号，已退出，未向平台提交。请在反馈首行写上 <!-- submission:记录号 -->：", file=sys.stderr)
            for path in missing:
                print(f"  {path.relative_to(root)}", file=sys.stderr)
        return 1

    try:
        records = list_submissions(cookie, args.article_id, args.class_id)
    except RuntimeError as exc:
        print(f"准备失败：{exc}", file=sys.stderr)
        return 1
    failures = 0

    referer = (
        f"{ORIGIN}/review/lesson/{args.class_id}?article={args.article_id}&class_sku={CLASS_SKU}"
    )
    for student_no, (path, feedback) in feedbacks.items():
        label = f"{student_no} / {feedback['record_id'] or '未标注'} {feedback['level_name']}{feedback['score']}"
        try:
            record = select_submission(records, student_no, feedback["record_id"])
        except ValueError as exc:
            print(f"FAIL {label}：{exc}")
            failures += 1
            continue
        record_id = record["id"]
        label = f"{student_no} / {record_id} {feedback['level_name']}{feedback['score']}"
        if same_correction(record, feedback["level"], feedback["remark"]):
            print(f"SKIP {label}：平台记录已一致")
            continue
        action = "UPDATE" if args.apply else "DRY-RUN"
        print(f"{action} {label}：优点/不足/改进 {feedback['counts']}，来源 {path.relative_to(root)}")
        if not args.apply:
            continue
        try:
            request_json(cookie, CORRECT_URL, {
                "id": record_id,
                "correct_level": feedback["level"],
                "correct_remark": feedback["remark"],
            }, referer)
        except RuntimeError as exc:
            print(f"FAIL {label}：{exc}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
