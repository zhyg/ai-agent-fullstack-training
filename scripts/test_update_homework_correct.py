import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
