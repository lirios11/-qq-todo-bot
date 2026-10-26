# -*- coding: utf-8 -*-
"""核心逻辑单测：时间换算、去重判定、合并落库。

运行：python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402


BASE = datetime(2026, 10, 26, 15, 30)          # 周一


class DeadlinePhraseTest(unittest.TestCase):
    def check(self, phrase, expected, basis, base=BASE):
        got, got_basis = main.parse_deadline_phrase(phrase, base)
        self.assertEqual(got.strftime("%Y-%m-%d %H:%M") if got else None, expected, msg=phrase)
        self.assertEqual(got_basis, basis, msg=phrase)

    def test_today_evening(self):
        self.check("今晚9点前", "2026-10-26 21:00", "inferred")

    def test_tomorrow_evening(self):
        self.check("明天下午6点前", "2026-10-27 18:00", "inferred")

    def test_after_tomorrow_morning(self):
        self.check("后天上午9点", "2026-10-28 09:00", "inferred")

    def test_this_friday(self):
        self.check("本周五下午6点前", "2026-10-30 18:00", "inferred")

    def test_next_friday(self):
        self.check("下周五", "2026-11-06 23:59", "inferred")

    def test_bare_weekday_rolls_forward(self):
        # 周一发的消息只说"周五"，就是这周五
        self.check("周五前", "2026-10-30 23:59", "inferred")
        # 周六再说"周五"就该是下一个周五
        late = datetime(2026, 10, 31, 10, 0)
        self.check("周五前", "2026-11-06 23:59", "inferred", base=late)

    def test_explicit_month_day(self):
        self.check("10月9日12:00前", "2026-10-09 12:00", "explicit",
                   base=datetime(2026, 10, 6, 21, 15))

    def test_month_end(self):
        self.check("月底前", "2026-10-31 23:59", "inferred")

    def test_clock_only_rolls_to_tomorrow(self):
        # 15:30 已经过了 12:00，只能理解为明天中午
        self.check("12点前交", "2026-10-27 12:00", "inferred")

    def test_no_deadline(self):
        self.check(None, None, "none")
        self.check("尽快完成", None, "none")


class SimilarTitleTest(unittest.TestCase):
    def test_same_notice_different_wording(self):
        self.assertTrue(main.similar_title(
            "填写乙肝疫苗接种统计表并私聊发给负责人", "提交乙肝疫苗接种统计表"))

    def test_different_dates_not_merged(self):
        self.assertFalse(main.similar_title("10月9日交实验报告", "10月11日交实验报告"))

    def test_different_tasks_not_merged(self):
        self.assertFalse(main.similar_title("填写入团申请书", "缴纳团费"))
        self.assertFalse(main.similar_title("提交甲表", "提交乙表"))


class MergeTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"todos": []}, f, ensure_ascii=False)
        self.old_path = main.TODOS_PATH
        main.TODOS_PATH = self.path

    def tearDown(self):
        main.TODOS_PATH = self.old_path
        os.unlink(self.path)

    def messages(self, *texts):
        return [{
            "msg_id": str(i + 1),
            "group_id": 100 + i,
            "group": "群%d" % (i + 1),
            "sender": "同学%d" % (i + 1),
            "time": "2026-10-26 10:%02d" % (i * 5),
            "text": text,
        } for i, text in enumerate(texts)]

    def load(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)["todos"]

    def test_same_event_across_groups_merges_sources(self):
        msgs = self.messages("今晚9点前交乙肝疫苗接种统计表", "请提交乙肝疫苗接种统计表，今晚9点前")
        items = [
            {"title": "提交乙肝疫苗接种统计表", "deadline_phrase": "今晚9点前", "source_index": 1,
             "source_quote": "今晚9点前交乙肝疫苗接种统计表"},
            {"title": "填写乙肝疫苗接种统计表", "deadline_phrase": "今晚9点前", "source_index": 2,
             "source_quote": "请提交乙肝疫苗接种统计表，今晚9点前"},
        ]
        main.merge_todos(items, msgs)
        todos = self.load()
        self.assertEqual(len(todos), 1, "同一件事应该合成一条")
        self.assertEqual(len(todos[0]["sources"]), 2, "两个群的来源都要留着")
        self.assertEqual(todos[0]["deadline"], "2026-10-26 21:00")
        self.assertEqual(todos[0]["deadline_basis"], "inferred")
        self.assertEqual(todos[0]["published_at"], "2026-10-26 10:00")

    def test_done_todo_not_resurrected(self):
        msgs = self.messages("今晚9点前交乙肝疫苗接种统计表")
        main.merge_todos([{"title": "提交乙肝疫苗接种统计表", "deadline_phrase": "今晚9点前",
                           "source_index": 1}], msgs)
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        data["todos"][0]["done"] = True
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        msgs2 = [{
            "msg_id": "99", "group_id": 5, "group": "另一个群", "sender": "某人",
            "time": "2026-10-26 12:00", "text": "再说一次，今晚9点前交乙肝疫苗接种统计表",
        }]
        added = main.merge_todos([{"title": "填写乙肝疫苗接种统计表", "deadline_phrase": "今晚9点前",
                                   "source_index": 1}], msgs2)
        self.assertEqual(added, 0, "已完成的事不该因为群消息转发又冒出来")
        self.assertEqual(len(self.load()), 1)

    def test_same_task_different_deadline_is_new(self):
        msgs = self.messages("10月28日前交实验报告", "11月4日前交实验报告")
        main.merge_todos([
            {"title": "交实验报告", "deadline_phrase": "10月28日前", "source_index": 1},
            {"title": "交实验报告", "deadline_phrase": "11月4日前", "source_index": 2},
        ], msgs)
        todos = self.load()
        self.assertEqual(len(todos), 2, "不同截止日期的同名任务要分开")


if __name__ == "__main__":
    unittest.main()
