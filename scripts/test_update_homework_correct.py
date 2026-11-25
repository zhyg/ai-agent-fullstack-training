import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import update_homework_correct as corrections
from update_homework_correct import parse_feedback


class FeedbackTests(unittest.TestCase):
    def test_duration_is_allowed_but_scores_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feedback.md"
            for remark, rejected in (
                ("有效期从 30 分钟更新为 20 分钟。", False),
                ("RRF 分数与独立名次计算一致。", False),
                ("分数需要提高。", True),
                ("该项扣分 0.50 分。", True),
                ("该项为 20 分。", True),
                ("该项为 99.50分。", True),
            ):
                with self.subTest(remark=remark):
                    path.write_text(
                        "<!-- submission:19442 -->\n"
                        "**1. 作业等级：优秀（99.50分）**\n"
                        f"**2. 作业优点**\n\n- {remark}\n\n"
                        "**3. 作业不足**\n\n- 截图记录不一致。\n\n"
                        "**4. 改进方案**\n\n- 补充一致的记录。\n",
                        encoding="utf-8",
                    )
                    if rejected:
                        with self.assertRaisesRegex(ValueError, "评语不得包含分数"):
                            parse_feedback(path)
                    else:
                        feedback = parse_feedback(path)
                        self.assertIn(remark, feedback["remark"])
                        self.assertEqual(feedback["level"], 8)


class SubmissionListTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.week = self.root / "homework/week02"
        self.week.mkdir(parents=True)
        self.list_path = self.root / "submissions.json"

    def feedback(self, filename, record_id, score=87):
        path = self.week / filename
        level = "优秀" if score >= 80 else "不及格"
        path.write_text(
            f"<!-- submission:{record_id} -->\n"
            f"**1. 作业等级：{level}（{score}分）**\n"
            f"**2. 作业优点**\n\n- 记录{record_id}的实现可运行。\n\n"
            "**3. 作业不足**\n\n- 展示不完整。\n\n"
            "**4. 改进方案**\n\n- 补充展示。\n",
            encoding="utf-8",
        )
        return path

    def run_cli(self, submissions, *options):
        self.list_path.write_text(json.dumps(submissions), encoding="utf-8")
        posts = []

        def request(cookie, url, payload, referer):
            self.assertEqual(url, corrections.CORRECT_URL)
            posts.append(payload)
            return {"code": 0}

        records = [{**item, "status": 1} for item in submissions if isinstance(item, dict)]
        args = ["update_homework_correct.py", "--week", "week02", "--article-id", "1025885", *options]
        output = io.StringIO()
        with (patch.object(corrections, "__file__", str(self.root / "scripts/update_homework_correct.py")),
              patch.dict("os.environ", {"GEEKBANG_COOKIE": "test-cookie"}),
              patch.object(corrections, "list_submissions", return_value=records),
              patch.object(corrections, "request_json", side_effect=request),
              patch("sys.argv", args), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output)):
            result = corrections.main()
        return result, posts, output.getvalue()

    def test_list_selects_exact_record_not_old_or_latest_file(self):
        (self.week / "G123.md").write_text("旧评语不可解析", encoding="utf-8")
        self.feedback("G123-submission20.md", 20, 43)
        self.feedback("G123-submission30.md", 30)
        (self.week / "G456.md").write_text("不在本批次的无效反馈", encoding="utf-8")
        result, posts, output = self.run_cli([{"student_no": "G123", "id": 20}], "--list", str(self.list_path), "--apply")
        self.assertEqual(result, 0, output)
        self.assertEqual([(p["id"], p["correct_level"]) for p in posts], [(20, 1)])
        self.assertIn("记录20的实现", posts[0]["correct_remark"])

    def test_list_keeps_two_submissions_for_same_student(self):
        self.feedback("G123.md", 10)
        self.feedback("G123-submission20.md", 20, 43)
        result, posts, output = self.run_cli(
            [{"student_no": "G123", "id": 10}, {"student_no": "G123", "id": 20}],
            "--list", str(self.list_path), "--apply",
        )
        self.assertEqual(result, 0, output)
        self.assertEqual([(p["id"], p["correct_level"]) for p in posts], [(10, 8), (20, 1)])

    def test_invalid_or_ambiguous_batch_submits_nothing(self):
        self.feedback("G123.md", 10)
        for case in ("missing", "wrong_marker", "duplicate_feedback", "duplicate_list", "invalid_id", "invalid_feedback"):
            with self.subTest(case=case):
                later = self.week / "G123-submission20.md"
                later.unlink(missing_ok=True)
                submissions = [{"student_no": "G123", "id": 10}, {"student_no": "G123", "id": 20}]
                if case == "wrong_marker":
                    self.feedback(later.name, 99)
                elif case == "duplicate_feedback":
                    self.feedback(later.name, 10)
                elif case == "duplicate_list":
                    submissions[1]["id"] = 10
                elif case == "invalid_id":
                    submissions[1]["id"] = True
                elif case == "invalid_feedback":
                    later.write_text("<!-- submission:20 -->\n无法解析的反馈", encoding="utf-8")
                result, posts, output = self.run_cli(submissions, "--list", str(self.list_path), "--apply")
                self.assertEqual(result, 1, output)
                self.assertEqual(posts, [])

    def test_preview_and_student_filter(self):
        self.feedback("G123.md", 10)
        submissions = [{"student_no": "G123", "id": 10}, {"student_no": "G456", "id": 20}]
        result, posts, output = self.run_cli(submissions, "--list", str(self.list_path), "--student-no", "G123")
        self.assertEqual(result, 0, output)
        self.assertEqual(posts, [])
        self.assertIn("DRY-RUN G123 / 10", output)
        self.assertNotIn("G456", output)

    def test_legacy_mode_still_uses_student_named_feedback(self):
        self.feedback("G123.md", 10)
        self.feedback("G123-submission20.md", 20, 43)
        result, posts, output = self.run_cli([{"student_no": "G123", "id": 10}], "--apply")
        self.assertEqual(result, 0, output)
        self.assertEqual([p["id"] for p in posts], [10])


if __name__ == "__main__":
    unittest.main()
