#!/usr/bin/env python3
"""把暂存区的批改结果归档到 homework/<week>/，绝不覆盖已有记录。

用法：python archive.py --week week02 --list homework/week02/homework-list02-pending-....json
暂存区：.amp/in/orb-backup/grading/<学号>-<记录号>-{feedback.md,evaluation.md,evidence.tar.gz}

命名规则（每次提交一组独立文件）：
- 该学号在本周还没有 <学号>.md：
    <学号>.md、attachments/<学号>.md、attachments/<学号>-evidence.tar.gz
- 已有 <学号>.md（之前批改过）：
    <学号>-submission<记录号>.md、attachments/<学号>-submission<记录号>.md、
    attachments/<学号>-submission<记录号>-evidence.tar.gz
反馈首行写入 <!-- submission:<记录号> -->；某记录号已归档过则跳过。
所有写入都用独占创建，目标存在即失败，不修改任何已有文件。
"""

import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STAGING = ROOT / ".amp/in/orb-backup/grading"


def archived_records(week_dir: Path, student_no: str) -> set[str]:
    records = set()
    for path in week_dir.glob(f"{student_no}*.md"):
        match = re.match(r"<!-- submission:(\d+) -->", path.read_text(errors="replace"))
        if match:
            records.add(match.group(1))
    return records


def check_evidence(path: Path) -> int:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
    bad = [m.name for m in members
           if m.name.startswith("/") or ".." in Path(m.name).parts
           or Path(m.name).name == ".env" or "site-packages/" in m.name or "node_modules/" in m.name]
    if not members or bad:
        sys.exit(f"{path.name} 证据包为空或含不安全成员：{bad[:5]}")
    return len(members)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", required=True)
    parser.add_argument("--list", required=True, type=Path)
    args = parser.parse_args()
    week_dir = ROOT / "homework" / args.week
    attachments = week_dir / "attachments"
    attachments.mkdir(parents=True, exist_ok=True)

    for user in json.loads((ROOT / args.list).read_text()):
        sid, record = user["student_no"], str(user["id"])
        staged = {kind: STAGING / f"{sid}-{record}-{kind}"
                  for kind in ("feedback.md", "evaluation.md", "evidence.tar.gz")}
        missing = [p.name for p in staged.values() if not p.exists()]
        if missing:
            print(f"PENDING {sid} / {record}：暂存区缺少 {missing}")
            continue
        if record in archived_records(week_dir, sid):
            print(f"SKIP {sid} / {record}：该记录已归档")
            continue

        stem = sid if not (week_dir / f"{sid}.md").exists() else f"{sid}-submission{record}"
        targets = {
            "feedback.md": week_dir / f"{stem}.md",
            "evaluation.md": attachments / f"{stem}.md",
            "evidence.tar.gz": attachments / f"{stem}-evidence.tar.gz",
        }
        clash = [str(p.relative_to(ROOT)) for p in targets.values() if p.exists()]
        if clash:
            sys.exit(f"{sid} / {record} 目标已存在，拒绝覆盖：{clash}")

        count = check_evidence(staged["evidence.tar.gz"])
        evidence = staged["evidence.tar.gz"].read_bytes()
        digest = hashlib.sha256(evidence).hexdigest()
        rel = lambda p: p.relative_to(ROOT).as_posix()
        evaluation = staged["evaluation.md"].read_text().rstrip() + (
            f"\n\n## 归档记录\n\n- 平台提交记录：{record}。\n"
            f"- 学员反馈：`{rel(targets['feedback.md'])}`。\n"
            f"- 本附件：`{rel(targets['evaluation.md'])}`。\n"
            f"- 证据包：`{rel(targets['evidence.tar.gz'])}`；SHA256：`{digest}`。\n"
        )
        feedback = f"<!-- submission:{record} -->\n\n" + staged["feedback.md"].read_text().rstrip() + "\n"

        with targets["evidence.tar.gz"].open("xb") as stream:
            stream.write(evidence)
        with targets["evaluation.md"].open("x") as stream:
            stream.write(evaluation)
        with targets["feedback.md"].open("x") as stream:
            stream.write(feedback)
        print(f"ARCHIVED {sid} / {record} -> {rel(targets['feedback.md'])}（证据 {count} 项，sha256={digest}）")


if __name__ == "__main__":
    main()
