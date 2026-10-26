r"""生成一份假的演示数据，用来截图 / 给别人看效果。

真实 todos.json 里有班级群名、同学昵称，不能直接放到公开仓库，
所以这里用编造的群名和人名，按当前日期生成一批待办。

用法：
    python tools/make_demo_data.py                 # 写到 docs/demo-data/todos.json
    python tools/make_demo_data.py <目录>

然后这样启动一个演示看板（不会碰你的真实数据）：
    set QQTODO_DATA_DIR=docs\demo-data
    python main.py serve --port 8090
"""
import json
import os
import sys
from datetime import datetime, timedelta


def stamp(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def build():
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def day(n, hh, mm=0):
        return stamp(today + timedelta(days=n, hours=hh, minutes=mm))

    def src(group, sender, msg_id, when, quote, conf="exact"):
        return {"group": group, "group_id": 1000 + msg_id, "sender": sender,
                "msg_id": str(msg_id), "time": when, "quote": quote, "confidence": conf}

    items = [
        {
            "title": "填写并提交乙肝疫苗接种统计表（附件3）",
            "detail": "填附件3，私聊发给班长；先看附件1确认自己是否已经在名单里",
            "start_at": None,
            "deadline": day(0, 21, 0),
            "deadline_basis": "inferred",
            "deadline_raw": "今晚9点前",
            "published_at": day(0, 15, 10),
            "event_key": "demo-1",
            "sources": [
                src("计科2班班群", "班长·小林", 101, day(0, 15, 10),
                    "请各位同学今晚9点前把乙肝疫苗接种统计表（附件3）填好，私聊发给我"),
                src("2026级计科年级群", "辅导员·周老师", 102, day(0, 15, 25),
                    "转发：乙肝疫苗接种统计表（附件3）今晚9点前交给班级负责人", "matched"),
            ],
            "done": False,
            "created": day(0, 15, 10),
        },
        {
            "title": "提交实验报告纸质版",
            "detail": "纸质版交到教4203，电子版发课程邮箱；逾期不收",
            "start_at": None,
            "deadline": day(0, 23, 30),
            "deadline_basis": "inferred",
            "deadline_raw": "今天晚上十一点半前",
            "published_at": day(0, 9, 40),
            "event_key": "demo-2",
            "sources": [src("计科2班班群", "学委·阿哲", 103, day(0, 9, 40),
                            "今天晚上十一点半前把实验报告纸质版交到教4203")],
            "done": False,
            "created": day(0, 9, 40),
        },
        {
            "title": "报名“正大杯”市场调查大赛并缴费",
            "detail": "本科A类竞赛；团队3-5人，可跨专业组队；缴费后才能提交作品",
            "start_at": None,
            "deadline": day(2, 20, 0),
            "deadline_basis": "explicit",
            "deadline_raw": "10月28日20:00截止",
            "published_at": day(-1, 11, 11),
            "event_key": "demo-3",
            "sources": [src("计科2班班群", "封心锁爱", 104, day(-1, 11, 11),
                            "报名截止10月28日20:00，缴费后才能提交作品")],
            "done": False,
            "created": day(-1, 11, 11),
        },
        {
            "title": "到教4303晚自习并签到",
            "detail": "今晚7点到9点，班长点名",
            "start_at": day(0, 19, 0),
            "deadline": None,
            "deadline_basis": "none",
            "deadline_raw": None,
            "published_at": day(0, 12, 5),
            "event_key": "demo-4",
            "sources": [src("计科2班班群", "班长·小林", 105, day(0, 12, 5),
                            "今晚7点到9点在教4303晚自习，记得签到")],
            "done": False,
            "created": day(0, 12, 5),
        },
        {
            "title": "扫码加入 iCAN 大赛培训群",
            "detail": "学院王老师负责；本月邀请企业 AI 创作导师培训，直接扫码进群",
            "start_at": None,
            "deadline": None,
            "deadline_basis": "none",
            "deadline_raw": None,
            "published_at": day(0, 11, 11),
            "event_key": "demo-5",
            "sources": [src("2026级计科年级群", "辅导员·周老师", 106, day(0, 11, 11),
                            "iCAN 大赛本月培训群二维码在群里，尽快扫码加入")],
            "done": False,
            "created": day(0, 11, 11),
        },
        {
            "title": "报名校级趣味运动会",
            "detail": "通过班级链接报名，统一补签",
            "start_at": None,
            "deadline": None,
            "deadline_basis": "none",
            "deadline_raw": None,
            "published_at": day(-2, 10, 0),
            "event_key": "demo-6",
            "sources": [src("计科2班班群", "体育委员·大鹏", 107, day(-2, 10, 0),
                            "趣味运动会报名链接发群里了，想去的填一下")],
            "done": False,
            "created": day(-2, 10, 0),
        },
        {
            "title": "完成实验室安全教育考试并提交证书截图",
            "detail": "在实验平台考试，80 分及格，截图发给实验室老师",
            "start_at": None,
            "deadline": day(-1, 17, 0),
            "deadline_basis": "inferred",
            "deadline_raw": "本周日前完成",
            "published_at": day(-4, 16, 0),
            "event_key": "demo-7",
            "sources": [src("2026级计科年级群", "实验室·陈老师", 108, day(-4, 16, 0),
                            "本周日前完成实验室安全教育考试，把证书截图发我")],
            "done": False,
            "created": day(-4, 16, 0),
        },
        {
            "title": "绑定雨课堂身份",
            "detail": "大学英语课要求，绑定后课堂互动才计分",
            "start_at": None,
            "deadline": None,
            "deadline_basis": "none",
            "deadline_raw": None,
            "published_at": day(-3, 8, 30),
            "event_key": "demo-8",
            "sources": [src("大学英语（3）课程群", "任课老师·李", 109, day(-3, 8, 30),
                            "还没绑定雨课堂的同学尽快绑定，影响平时分")],
            "done": False,
            "created": day(-3, 8, 30),
        },
        {
            "title": "准备第 9 周词汇语法测试",
            "detail": "范围：Unit 1-2 词汇 + 语法填空",
            "start_at": None,
            "deadline": day(4, 8, 0),
            "deadline_basis": "inferred",
            "deadline_raw": "下周一上课时测",
            "published_at": day(-1, 20, 0),
            "event_key": "demo-9",
            "sources": [src("大学英语（3）课程群", "任课老师·李", 110, day(-1, 20, 0),
                            "下周一上课时做第9周词汇语法测试，范围Unit1-2")],
            "done": False,
            "created": day(-1, 20, 0),
        },
        {
            "title": "填写学生会纳新报名表（电子版 + 纸质版）",
            "detail": "纸质版交到团委办公室，电子版发邮箱",
            "start_at": None,
            "deadline": day(-5, 18, 0),
            "deadline_basis": "inferred",
            "deadline_raw": "上周五下午6点前",
            "published_at": day(-8, 9, 0),
            "event_key": "demo-10",
            "sources": [src("青年发展部纳新群", "部长·Atthree", 111, day(-8, 9, 0),
                            "报名表周五下午6点前交，纸质版送到团委")],
            "done": True,
            "created": day(-8, 9, 0),
        },
        {
            "title": "参加新生入学教育会议",
            "detail": "图书馆报告厅，提前十分钟入场",
            "start_at": None,
            "deadline": None,
            "deadline_basis": "none",
            "deadline_raw": None,
            "published_at": day(-16, 14, 0),
            "event_key": "demo-11",
            "sources": [src("计科2班班群", "班长·小林", 112, day(-16, 14, 0),
                            "明天下午两点图书馆报告厅开新生入学教育会，提前十分钟到")],
            "done": True,
            "created": day(-16, 14, 0),
        },
        {
            "title": "按要求购买医保",
            "detail": "在校园统一缴费平台操作",
            "start_at": None,
            "deadline": None,
            "deadline_basis": "none",
            "deadline_raw": None,
            "published_at": day(-20, 10, 0),
            "event_key": "demo-12",
            "sources": [src("计科2班班群", "辅导员·周老师", 113, day(-20, 10, 0),
                            "医保还没买的同学这两天在平台买一下")],
            "done": True,
            "created": day(-20, 10, 0),
        },
    ]

    for i, t in enumerate(items):
        t["id"] = "demo-%02d" % (i + 1)
        t.setdefault("sources", [])
        t["source_count"] = len(t["sources"])
        t["source_confidence"] = t["sources"][0]["confidence"] if t["sources"] else "unknown"
        t["source_quote"] = t["sources"][0]["quote"] if t["sources"] else None
        t["source_msg_id"] = t["sources"][0]["msg_id"] if t["sources"] else None
        t["group"] = t["sources"][0]["group"] if t["sources"] else ""
        t["sender"] = t["sources"][0]["sender"] if t["sources"] else ""
        t["start_time"] = t["start_at"]
    return {"todos": items, "schema_version": 2}


def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "demo-data")
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, "todos.json")
    data = build()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("已写入 %s（%d 条，%d 条未完成）" % (
        path, len(data["todos"]), sum(1 for t in data["todos"] if not t["done"])))


if __name__ == "__main__":
    main()
