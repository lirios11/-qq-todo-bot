#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ 群消息 → AI 自动提取待办 → 网页看板

一个进程里跑三件事：
  1) 看板服务（HTTP）—— 只读 todos.json，NapCat 掉线也照样能看历史待办；
  2) 同步线程 —— 定时拉群消息、交给 AI 提炼待办；
  3) NapCat 守护线程 —— 掉线自动拉起，并用快速登录参数免扫码。

用法：
  python main.py                 # 前台常驻，会打开浏览器
  python main.py --background    # 后台常驻（不弹浏览器，日志写 logs/app.log）
  python main.py --port 8090     # 换端口（也支持环境变量 QQTODO_BOARD_PORT）
  python main.py once            # 先同步一次再开看板
  python main.py serve           # 只看板，不连 NapCat

免扫码说明：config.json 填 napcat_qq_uin 后，程序用 NapCat 自带的快速登录
（NapCatWinBootMain.exe <QQ号>）启动，QQ 成功登录过一次以后就不必再扫码。
"""

import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, time as dtime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

# pythonw.exe（后台无窗口模式）里 sys.stdout 是 None，先兜底，否则任何 print 都会炸
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 数据目录可以和代码目录分开：演示 / 多开 / 放 U 盘时只改这一个环境变量
DATA_DIR = os.path.abspath((os.environ.get("QQTODO_DATA_DIR") or "").strip() or BASE_DIR)
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
TODOS_PATH = os.path.join(DATA_DIR, "todos.json")
SEEN_PATH = os.path.join(DATA_DIR, "seen.json")
IGNORE_PATH = os.path.join(DATA_DIR, "ignore_keywords.json")
WEB_DIR = os.path.join(BASE_DIR, "web")
LOG_DIR = os.path.join(DATA_DIR, "logs")
LOG_PATH = os.path.join(LOG_DIR, "app.log")
KEY_PLACEHOLDER = "在这里填你的DeepSeek API Key"

SYNC_LOCK = threading.Lock()
_LOG_LOCK = threading.Lock()
LOG_MAX_BYTES = 2 * 1024 * 1024


def log(message, tag="info"):
    """同时写控制台和 logs/app.log —— 后台无窗口运行时只能靠日志排查。"""
    line = "%s [%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tag, message)
    with _LOG_LOCK:
        try:
            print(line, flush=True)
        except Exception:
            pass
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            if os.path.getsize(LOG_PATH) > LOG_MAX_BYTES:
                backup = LOG_PATH + ".1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.replace(LOG_PATH, backup)
        except Exception:
            pass


STATE = {
    "napcat_ok": False,
    "syncing": False,
    "last_sync": None,
    "last_ok_sync": None,
    "last_result": "尚未同步",
    "last_error": None,
    "started_at": None,
    "poll_interval": 180,
}

# NapCat 守护状态：proc 是拉起后的进程句柄，next_try 是下次允许拉起的时间
NAPCAT = {
    "proc": None,
    "launched_at": 0.0,
    "next_try": 0.0,
    "backoff": 60,
    "warned_missing": False,
}


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def reload_config():
    return load_json(CONFIG_PATH, {})


CONFIG = reload_config()


def api_key(cfg=None):
    """API Key 取值顺序：环境变量 DEEPSEEK_API_KEY > config.json。

    做成函数是因为向导页保存后要立刻生效，不能停在 import 时算好的旧值。
    """
    env = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if env:
        return env
    cfg = cfg if cfg is not None else reload_config()
    key = (cfg.get("deepseek_api_key") or "").strip()
    return "" if key == KEY_PLACEHOLDER else key


def need_setup():
    return not api_key()


def napcat(method, params=None, timeout=15):
    """调用 NapCat 的 OneBot v11 HTTP 接口，成功返回 data，失败返回 None。"""
    cfg = reload_config()
    url = str(cfg.get("napcat_base_url", "http://127.0.0.1:6099")).rstrip("/") + "/" + method
    headers = {"Content-Type": "application/json"}
    token = (cfg.get("napcat_access_token") or "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        resp = requests.post(url, json=params or {}, headers=headers, timeout=timeout)
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") in ("failed", "error") or body.get("retcode", 0) != 0:
            return None
        return body.get("data")
    except Exception:
        return None


def napcat_ready():
    # 守护线程会高频探测，这里用短超时，避免一次探测卡住整个循环
    data = napcat("get_login_info", {}, timeout=4)
    if not data:
        data = napcat("get_group_list", {}, timeout=6)
    return bool(data)


def _scan_napcat():
    """在常见目录浅层找 NapCatWinBootMain.exe，不做全盘扫描。"""
    home = os.path.expanduser("~")
    roots = [BASE_DIR, os.path.dirname(BASE_DIR), home,
             os.path.join(home, "Desktop"), os.path.join(home, "Downloads")]
    for drive in ("C:\\", "D:\\", "E:\\", "F:\\"):
        if os.path.isdir(drive):
            roots.append(drive)
    found = []
    for root in roots:
        try:
            entries = [e for e in os.scandir(root) if e.is_dir() and "napcat" in e.name.lower()]
        except Exception:
            continue
        for entry in entries:
            for sub_root, dirs, files in os.walk(entry.path):
                rel = os.path.relpath(sub_root, entry.path)
                if rel != "." and rel.count(os.sep) > 1:
                    dirs[:] = []
                    continue
                for f in files:
                    if f.lower() == "napcatwinbootmain.exe":
                        found.append(os.path.join(sub_root, f))
    return found


def find_napcat_exe(cfg):
    candidates = []
    configured = (cfg.get("napcat_exe") or "").strip()
    if configured:
        candidates.append(configured)
    env = (os.environ.get("NAPCAT_EXE") or "").strip()
    if env:
        candidates.append(env)
    home = os.path.expanduser("~")
    candidates.extend([
        os.path.join("C:\\NapCat", "NapCatWinBootMain.exe"),
        os.path.join("C:\\NapCat", "NapCat.Shell.exe"),
        os.path.join("D:\\NapCat", "NapCatWinBootMain.exe"),
        os.path.join("F:\\NapCat", "NapCatWinBootMain.exe"),
        os.path.join(home, "NapCat", "NapCatWinBootMain.exe"),
        os.path.join(home, "Desktop", "NapCat", "NapCatWinBootMain.exe"),
    ])
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    scanned = _scan_napcat()
    return scanned[0] if scanned else None


def napcat_pid_running():
    """NapCat 进程已经在跑（可能还在登录），就不要重复拉第二个。"""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq NapCatWinBootMain.exe", "/NH"],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout or ""
        return "NapCatWinBootMain" in out
    except Exception:
        return False


def launch_napcat(cfg, exe):
    """带 QQ 号用快速登录启动 NapCat；没配 napcat_qq_uin 则退回扫码登录。"""
    uin = str(cfg.get("napcat_qq_uin") or "").strip()
    args = [exe] + ([uin] if uin.isdigit() else [])
    try:
        kwargs = {"cwd": os.path.dirname(exe)}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        NAPCAT["proc"] = subprocess.Popen(args, **kwargs)
        NAPCAT["launched_at"] = time.time()
        log("已启动 NapCat（%s）" % (
            "快速登录 QQ " + uin if uin.isdigit() else "未配置 napcat_qq_uin，接下来需要扫码"
        ))
        return True
    except Exception as e:
        STATE["last_error"] = "无法启动 NapCat：" + str(e)
        log(STATE["last_error"], "error")
        return False


def napcat_supervisor():
    """守护线程：连接正常就安静地探测，掉线按退避重启，全程不阻塞看板与同步。"""
    while True:
        try:
            cfg = reload_config()
            ready = napcat_ready()
            if ready != STATE["napcat_ok"]:
                STATE["napcat_ok"] = ready
                log("NapCat 已连接" if ready else "NapCat 连接断开，看板仍可查看历史待办",
                    "info" if ready else "warn")
            if ready:
                NAPCAT["backoff"] = 60
                NAPCAT["next_try"] = 0.0
                time.sleep(20)
                continue

            proc = NAPCAT["proc"]
            if proc is not None and proc.poll() is None:
                time.sleep(15)          # 进程还在，可能正在登录，先别启动第二个
                continue

            now = time.time()
            if now < NAPCAT["next_try"]:
                time.sleep(6)
                continue

            exe = find_napcat_exe(cfg)
            if not exe:
                if not NAPCAT["warned_missing"]:
                    log("没找到 NapCat 程序：请在 config.json 填 napcat_exe，否则只能当看板用。", "warn")
                    NAPCAT["warned_missing"] = True
                NAPCAT["next_try"] = now + 600
                time.sleep(10)
                continue

            if not napcat_pid_running():
                launch_napcat(cfg, exe)
            NAPCAT["next_try"] = now + NAPCAT["backoff"]
            NAPCAT["backoff"] = min(NAPCAT["backoff"] * 2, 600)
            time.sleep(10)
        except Exception as e:
            log("NapCat 守护线程异常：%s" % e, "error")
            time.sleep(15)


def get_groups():
    data = napcat("get_group_list", {})
    if not data:
        return []
    if isinstance(data, dict):
        data = data.get("groups") or []
    return data


def get_group_history(group_id, count):
    data = napcat("get_group_msg_history", {"group_id": group_id, "count": count})
    if not data:
        return []
    if isinstance(data, dict):
        messages = data.get("messages") or data.get("data") or []
    elif isinstance(data, list):
        messages = data
    else:
        messages = []
    return messages


def parse_segments(segments):
    if isinstance(segments, str):
        return segments.strip()
    text = ""
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        t = seg.get("type")
        d = seg.get("data", {}) or {}
        if t == "text":
            text += d.get("text", "")
        elif t == "at":
            text += " @某人"
        elif t == "image":
            text += " [图片]"
        elif t == "file":
            text += " [文件:" + str(d.get("name", "") or "") + "]"
        elif t == "face":
            text += " [表情]"
        elif t == "record":
            text += " [语音]"
        elif t == "video":
            text += " [视频]"
    return text.strip()


def load_todos():
    data = load_json(TODOS_PATH, {"todos": []})
    if isinstance(data, list):
        data = {"todos": data}
    return data


def load_seen():
    return load_json(SEEN_PATH, {"msg_ids": [], "ignored_msg_ids": []})


def load_ignores():
    return load_json(IGNORE_PATH, {"keywords": []})


def collect_new_messages():
    cfg = reload_config()
    targets = [int(x) for x in cfg.get("target_groups") or [] if str(x).isdigit()]
    count = int(cfg.get("history_count") or 50)
    groups = get_groups()
    if not groups:
        return [], "没拿到群列表。请确认 NapCat 已启动并已登录。"

    if targets:
        groups = [g for g in groups if int(g.get("group_id")) in targets]
        if not groups:
            return [], "配置的目标群 id 没在群列表里找到。"

    seen = load_seen()
    seen_ids = set(seen.get("msg_ids", []))
    ignored_ids = set(seen.get("ignored_msg_ids", []))
    keywords = [str(k) for k in load_ignores().get("keywords", [])]

    new_messages = []
    for g in groups:
        gid = int(g.get("group_id"))
        gname = g.get("group_name") or str(gid)
        history = get_group_history(gid, count)
        for m in history:
            mid = str(m.get("message_id") or "")
            if not mid or mid in seen_ids or mid in ignored_ids:
                continue
            text = parse_segments(m.get("message"))
            if not text:
                seen_ids.add(mid)
                continue
            if any(k and k in text for k in keywords):
                seen_ids.add(mid)
                continue
            sender = (m.get("sender") or {}).get("nickname") or "群友"
            sender = str(sender).strip() or "群友"
            ts = m.get("time")
            try:
                posted = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M") if ts else now_str()
            except Exception:
                posted = now_str()
            new_messages.append({
                "msg_id": mid,
                "group_id": gid,
                "group": gname,
                "sender": sender,
                "time": posted,
                "text": text,
            })
    save_json(SEEN_PATH, {
        **seen,
        "msg_ids": sorted(set(seen.get("msg_ids", [])) | seen_ids),
    })
    return new_messages, None


def system_prompt():
    today = datetime.now().strftime("%Y-%m-%d")
    weekday = "一二三四五六日"[datetime.now().weekday()]
    return f"""你是我的私人助理。今天是 {today}（星期{weekday}）。
我会给你一批已编号的 QQ 群消息。请挑出真正需要我处理的待办。

算待办：提交材料、报名、填表、缴费、交作业、参加活动、准备文件、回复某人、在规定时间内完成某项任务等。
不算待办：闲聊、纯参考通知、广告、投票链接、无关转发。

规则：
- 同一件事只输出一条：同一条消息里的同一件事不要拆成两条；几个群转发同一份通知也只算一条。
- source_index 必须是消息编号；source_quote 从该消息原文摘 1 句能证明这是待办的话（不超过 40 字）。
- 不要自己换算日期。原文里的时间说法原样抄进 deadline_phrase，例如 "今晚9点前"、"本周五下午"、"10月9日12:00前"、"明天下午6点前"；没有就写 null。
- start_time 只在原文明确写了开始日期时间时填 "YYYY-MM-DD HH:MM"，否则写 null，不要拿消息发送时间凑数。
- detail 说清楚要交什么、交给谁、在哪交；没有就写 null。

只输出 JSON：
{{"todos":[{{"title":"...","detail":null,"start_time":null,"deadline_phrase":"今晚9点前","source_index":1,"source_quote":"..."}}]}}"""


CN_NUM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}


def _to_int(token):
    if token is None:
        return None
    token = str(token).strip()
    if token.isdigit():
        return int(token)
    return CN_NUM.get(token)


def _parse_clock(text):
    """从"今晚9点前 / 下午18:30 前 / 12点"里抽出 (时, 分)，抽不到返回 None。"""
    m = re.search(r"(\d{1,2})\s*[:：]\s*(\d{1,2})", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi

    m = re.search(r"(上午|中午|下午|晚上|傍晚|凌晨|早上|今晚|明晚)?\s*(\d{1,2}|[一二三四五六七八九十]{1,3})\s*[点时](半|\d{1,2}分?)?", text)
    if not m:
        return None
    prefix = m.group(1) or ""
    h = _to_int(m.group(2))
    if h is None or not (0 <= h <= 23):
        return None
    if "半" in (m.group(3) or ""):
        mi = 30
    elif m.group(3):
        mi = _to_int(m.group(3).replace("分", "")) or 0
    else:
        mi = 0
    if prefix in ("下午", "晚上", "傍晚", "今晚", "明晚") and h < 12:
        h += 12
    if prefix == "中午" and h < 11:
        h = 12
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return h, mi


def _relative_day(text, base):
    """识别 今天 / 明天 / 后天 等，返回 date 或 None。"""
    if "大后天" in text:
        return base.date() + timedelta(days=3)
    if "后天" in text:
        return base.date() + timedelta(days=2)
    if any(k in text for k in ("明天", "明日", "明早", "明晚", "明儿")):
        return base.date() + timedelta(days=1)
    if any(k in text for k in ("今天", "今日", "今晚", "今早", "今儿")):
        return base.date()
    return None


def _weekday_of(text):
    m = re.search(r"(本|这|下下|下|上)?\s*(?:周|星期|礼拜)\s*([一二三四五六日天])", text)
    if not m:
        return None, None
    prefix = m.group(1) or ""
    char = m.group(2)
    target = 6 if char in "日天" else "一二三四五六".index(char)
    return prefix, target


def _weekday_date(text, base):
    prefix, target = _weekday_of(text)
    if target is None:
        return None
    monday = base.date() - timedelta(days=base.weekday())
    if prefix == "下":
        monday += timedelta(days=7)
    elif prefix == "下下":
        monday += timedelta(days=14)
    elif prefix == "上":
        monday -= timedelta(days=7)
    day = monday + timedelta(days=target)
    # 只说"周五"且这周已经过了，按下一个周五算
    if prefix == "" and day < base.date():
        day += timedelta(days=7)
    return day


def _month_day(text, base):
    m = re.search(r"(\d{1,2}|[一二三四五六七八九十]{1,3})\s*月\s*(\d{1,2}|[一二三四五六七八九十]{1,3})\s*[日号]?", text)
    if m:
        month, day = _to_int(m.group(1)), _to_int(m.group(2))
    else:
        m = re.search(r"(\d{1,2})\s*[号日](?=前|之前|当天|上午|下午|晚上|中午|$)", text)
        if not m:
            return None
        month, day = base.month, _to_int(m.group(1))
    if not month or not day or not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    for year in (base.year, base.year + 1):
        try:
            candidate = datetime(year, month, day).date()
        except ValueError:
            return None
        if candidate >= base.date() - timedelta(days=1):
            return candidate
    return None


def _special_day(text, base):
    """月底 / 本周内 / 周末 这类没有具体日子的说法。"""
    if "月底" in text or "月末" in text:
        first_next = datetime(base.year + (base.month // 12), (base.month % 12) + 1, 1)
        return (first_next - timedelta(days=1)).date()
    if "周末" in text:
        prefix, _ = _weekday_of(text)
        monday = base.date() - timedelta(days=base.weekday())
        if prefix == "下":
            monday += timedelta(days=7)
        return monday + timedelta(days=6)
    if "本周内" in text or "这周内" in text or "本周" in text:
        monday = base.date() - timedelta(days=base.weekday())
        return (monday + timedelta(days=6)) if (monday + timedelta(days=6)) >= base.date() else monday + timedelta(days=13)
    return None


def parse_deadline_phrase(phrase, base_dt):
    """把原文的相对时间说法换算成绝对时间，返回 (datetime|None, basis)。

    basis:
      explicit —— 原文写了完整日期（如 10月9日12:00），只是原样转成标准格式
      inferred —— 原文是相对说法（今晚/本周五/明天），由代码按消息时间推算
      none     —— 原文没有截止时间
    """
    if not phrase:
        return None, "none"
    text = str(phrase).strip()
    if not text:
        return None, "none"
    text = text.replace("：", ":").replace("．", ".")

    clock = _parse_clock(text)
    day = (_relative_day(text, base_dt) or _weekday_date(text, base_dt)
           or _month_day(text, base_dt) or _special_day(text, base_dt))

    has_full_date = bool(re.search(r"\d{4}\s*[-/年]", text)) or bool(re.search(r"[\d一二三四五六七八九十]{1,3}\s*月\s*[\d一二三四五六七八九十]{1,3}", text))

    if day is None and clock is None:
        return None, "none"
    if day is None:
        # 只说了时间没说日期：按消息当天算，已经过了就顺延到明天
        h, mi = clock
        candidate = datetime.combine(base_dt.date(), dtime(h, mi))
        if candidate < base_dt:
            candidate += timedelta(days=1)
        return candidate, "inferred"

    h, mi = clock if clock else (23, 59)
    return datetime.combine(day, dtime(h, mi)), ("explicit" if has_full_date else "inferred")



def extract_todos(messages):
    if not messages:
        return []
    cfg = reload_config()
    key = api_key(cfg)
    if not key:
        log("还没有配置 DeepSeek API Key，打开 http://127.0.0.1:8080/setup 填一下。", "error")
        return None

    lines = []
    for i, m in enumerate(messages, 1):
        text = m["text"]
        if len(text) > 500:
            text = text[:500] + "…"
        lines.append(
            f"[{i}] 【发送时间】{m['time']}【群名】{m['group']}【发送者】{m['sender']}\n{text}"
        )
    user_prompt = "以下是消息：\n\n" + "\n\n---\n\n".join(lines)
    if len(user_prompt) > 28000:
        user_prompt = user_prompt[:28000] + "\n…（消息过多，已截断）"

    url = str(cfg.get("deepseek_base_url", "https://api.deepseek.com")).rstrip("/") + "/chat/completions"
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    payload = {
        "model": cfg.get("deepseek_model", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log("调用 DeepSeek 失败：%s" % e, "error")
        return None

    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
    if m:
        content = m.group(1)
    try:
        parsed = json.loads(content)
    except Exception:
        s, e = content.find("{"), content.rfind("}")
        if s != -1 and e > s:
            try:
                parsed = json.loads(content[s:e + 1])
            except Exception:
                log("AI 返回的内容不是合法 JSON，已跳过这一批。", "error")
                return None
        else:
            log("AI 返回的内容不是合法 JSON，已跳过这一批。", "error")
            return None
    todos = parsed.get("todos") or []
    return [t for t in todos if t.get("title")]


STOP_TOKENS = [
    "通知", "关于", "各位", "同学", "大家", "请注意", "注意", "务必", "及时", "尽快", "按时",
    "需要", "可以", "要求", "规定", "相关", "有关", "本次", "事情", "事项", "事宜",
    "请", "的", "了", "和", "与", "及", "并", "在", "于", "为", "把", "将", "对", "由",
]


def normalize_title(s):
    s = re.sub(r"[\s，。,.!！?？、；;：:()（）\-—_【】\[\]“”\"']+", "", str(s or "")).lower()
    return s


def _grams(title):
    """标题去掉"通知/请/提交"这类通用词后剩下的二元字组，用来判断是不是同一件事。"""
    text = normalize_title(title)
    for token in STOP_TOKENS:
        text = text.replace(token, "")
    if len(text) < 2:
        return {text} if text else set()
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _dice(a, b):
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def _digits(text):
    return set(re.findall(r"\d{1,4}", str(text or "")))


def similar_title(a, b):
    """可能是同一件事吗？

    除了字面重合，还要看数字：10月9日的表和10月11日的表不是一回事，
    附件2和附件3也不是，数字对不上就不合并。
    """
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    da, db = _digits(a), _digits(b)
    if da and db and da != db and not (da <= db or db <= da):
        return False
    if min(len(na), len(nb)) >= 8 and (na in nb or nb in na):
        return True
    ga, gb = _grams(a), _grams(b)
    if _dice(ga, gb) >= 0.62:
        return True
    # 一句是另一句的"加长版"（多了"并私聊发给负责人"这类尾巴）也算同一件事
    if ga and gb and len(ga & gb) / min(len(ga), len(gb)) >= 0.7:
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.82


def event_key(title, deadline):
    """事件指纹：同一天 + 同一批关键词 = 同一件事，用于跨群去重和"已完成不复活"。"""
    day = str(deadline or "")[:10]
    raw = (day + "|" + ",".join(sorted(_grams(title)))).encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:12]


def parse_dt(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%m-%d %H:%M", "%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt.startswith("%m"):
                dt = dt.replace(year=datetime.now().year)
            if fmt in ("%Y-%m-%d", "%m-%d"):
                dt = dt.replace(hour=23, minute=59)
            return dt
        except ValueError:
            continue
    return None


def format_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def resolve_source(item, messages):
    """找到这条待办对应的原始消息，返回 (消息, 可信度)。

    可信度 exact  = 编号或引文能对上（可靠）
           guessed = 只能靠标题猜（前端会标"来源待确认"）
           unknown = 一条都对不上
    """
    idx = item.get("source_index")
    try:
        n = int(idx)
    except (TypeError, ValueError):
        n = None
    if n and 1 <= n <= len(messages):
        return messages[n - 1], "exact"

    quote = (item.get("source_quote") or "").strip()
    if quote:
        for m in messages:
            if quote[:14] in m["text"]:
                return m, "exact"

    title = item.get("title") or ""
    best, score = None, 0
    for m in messages:
        blob = normalize_title(m["text"])
        s = 0
        if title and normalize_title(title)[:8] in blob:
            s += 2
        if quote and normalize_title(quote)[:12] in blob:
            s += 3
        if s > score:
            best, score = m, s
    return (best, "guessed") if best else (None, "unknown")



def _snippet(text, phrase, limit=40):
    """从原文里截一小段当引文，优先挑出现截止说法的那句。"""
    text = str(text or "").replace("\n", " ").strip()
    if phrase and str(phrase) in text:
        start = max(0, text.find(str(phrase)) - 12)
        return text[start:start + limit]
    return text[:limit]


def related_sources(primary, title, phrase, messages, limit=4):
    """同一批次里，别的群转发的同一份通知也要挂成来源。

    模型通常只会引用它最先看到的那条消息，所以这里按"截止说法 + 标题关键词覆盖率"
    把同批次的其它消息补回来，标记 confidence=matched。
    """
    key = set(_grams(title))
    out = []
    for m in messages:
        if primary is not None and m.get("msg_id") == primary.get("msg_id"):
            continue
        text = m.get("text") or ""
        blob = normalize_title(text)
        hit = 0
        if phrase and str(phrase) in text:
            hit += 2
        if key:
            coverage = sum(1 for g in key if g in blob) / float(len(key))
            if coverage >= 0.5:
                hit += 2
        if hit >= 3:
            out.append(m)
        if len(out) >= limit:
            break
    return out


def build_source(src, item, confidence):
    return {
        "group": (src or {}).get("group") or "",
        "group_id": (src or {}).get("group_id"),
        "sender": (src or {}).get("sender") or "",
        "msg_id": (src or {}).get("msg_id"),
        "time": (src or {}).get("time"),
        "quote": (item.get("source_quote") or "").strip() or None,
        "confidence": confidence,
    }


def append_source(todo, source, limit=8):
    """把一条新来源挂到待办上；同一条消息只记一次。"""
    sources = todo.setdefault("sources", [])
    mid = source.get("msg_id")
    for s in sources:
        if mid and s.get("msg_id") == mid:
            return False
        if not mid and (s.get("group") or "", s.get("quote") or "") == (source.get("group") or "", source.get("quote") or ""):
            return False
    if len(sources) >= limit:
        return False
    sources.append(source)
    if not todo.get("group"):
        todo["group"] = source.get("group") or ""
    if not todo.get("sender"):
        todo["sender"] = source.get("sender") or ""
    if not todo.get("source_quote"):
        todo["source_quote"] = source.get("quote")
    return True


def _same_deadline_day(a, b):
    if not a or not b:
        return True
    return str(a)[:10] == str(b)[:10]


def _merge_into(twin, source, due_dt, basis, raw, start_dt, detail):
    append_source(twin, source)
    if due_dt and not twin.get("deadline"):
        twin["deadline"] = format_dt(due_dt)
        twin["deadline_basis"] = basis
        twin["deadline_raw"] = raw
    if start_dt and not twin.get("start_at"):
        twin["start_at"] = format_dt(start_dt)
        twin["start_time"] = twin["start_at"]
    if detail and len(detail) > len(twin.get("detail") or ""):
        twin["detail"] = detail


def merge_todos(new_todos, messages):
    """把 AI 结果并入 todos.json：同一件事只留一条，但把所有来源都记下来。"""
    data = load_todos()
    todos = data["todos"]
    pending = [t for t in todos if not t.get("done")]
    archived = [t for t in todos if t.get("done")]

    seen_msg_ids = set()
    for t in todos:
        if t.get("source_msg_id"):
            seen_msg_ids.add(str(t["source_msg_id"]))
        for s in t.get("sources") or []:
            if s.get("msg_id"):
                seen_msg_ids.add(str(s["msg_id"]))

    added = merged = skipped = 0
    for item in new_todos:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        src, confidence = resolve_source(item, messages)
        msg_id = str(src["msg_id"]) if src and src.get("msg_id") else None
        if msg_id and msg_id in seen_msg_ids:
            skipped += 1
            continue

        published = parse_dt(src["time"]) if src else None
        published = published or datetime.now()
        due_dt, basis = parse_deadline_phrase(item.get("deadline_phrase"), published)
        if basis == "none" and item.get("deadline"):
            # 模型偶尔直接给绝对时间，兜底接受，但标成推算，不冒充原文
            due_dt = parse_dt(item.get("deadline"))
            basis = "inferred" if due_dt else "none"
        start_dt = parse_dt(item.get("start_time"))
        detail = (item.get("detail") or "").strip() or None
        raw = (item.get("deadline_phrase") or "").strip() or None
        source = build_source(src, item, confidence)
        extras = [build_source(m, {"source_quote": _snippet(m.get("text"), raw)}, "matched")
                  for m in related_sources(src, title, raw, messages)]
        due_str = format_dt(due_dt)

        twin = next((t for t in pending
                     if similar_title(title, t.get("title"))
                     and _same_deadline_day(due_str, t.get("deadline"))), None)
        if twin:
            _merge_into(twin, source, due_dt, basis, raw, start_dt, detail)
            for extra in extras:
                append_source(twin, extra)
            merged += 1
            if msg_id:
                seen_msg_ids.add(msg_id)
            continue

        # 同一件事如果已经完成过、截止日也一样，就不要再复活（群消息反复转发很常见）
        if any(similar_title(title, t.get("title"))
               and _same_deadline_day(due_str, t.get("deadline"))
               for t in archived):
            skipped += 1
            if msg_id:
                seen_msg_ids.add(msg_id)
            continue

        todo = {
            "id": "%d%02d" % (int(time.time() * 1000), len(todos) % 100),
            "title": title,
            "detail": detail,
            "start_at": format_dt(start_dt),
            "deadline": due_str,
            "deadline_basis": basis,
            "deadline_raw": raw,
            "published_at": format_dt(published),
            "event_key": event_key(title, due_str),
            "sources": [source] + extras,
            "done": False,
            "created": now_str(),
            # 下面几个是给旧前端 / 老数据留的兼容字段
            "group": source.get("group") or "",
            "sender": source.get("sender") or "",
            "source_quote": source.get("quote"),
            "source_msg_id": msg_id,
            "start_time": format_dt(start_dt) or format_dt(published),
        }
        todos.append(todo)
        pending.append(todo)
        added += 1
        if msg_id:
            seen_msg_ids.add(msg_id)

    save_json(TODOS_PATH, data)
    log("并入结果：新增 %d 条，合并进已有 %d 条，跳过重复 %d 条" % (added, merged, skipped))
    return added



def dedupe_existing():
    """启动时把未完成的近义待办收成一条，来源一并合并进去。"""
    data = load_todos()
    todos = data.get("todos") or []
    pending = [t for t in todos if not t.get("done")]
    done = [t for t in todos if t.get("done")]
    kept, removed = [], 0
    for t in pending:
        twin = next((k for k in kept
                     if similar_title(t.get("title"), k.get("title"))
                     and _same_deadline_day(t.get("deadline"), k.get("deadline"))), None)
        if not twin:
            kept.append(t)
            continue
        removed += 1
        for s in t.get("sources") or []:
            append_source(twin, s)
        if t.get("deadline") and not twin.get("deadline"):
            twin["deadline"] = t["deadline"]
            twin["deadline_basis"] = t.get("deadline_basis")
            twin["deadline_raw"] = t.get("deadline_raw")
        if t.get("start_at") and not twin.get("start_at"):
            twin["start_at"] = t["start_at"]
            twin["start_time"] = t["start_at"]
        if len(t.get("detail") or "") > len(twin.get("detail") or ""):
            twin["detail"] = t.get("detail")
    if removed:
        data["todos"] = kept + done
        save_json(TODOS_PATH, data)
        log("已合并 %d 条重复待办。" % removed)
    return removed


SCHEMA_VERSION = 2


def ensure_schema():
    """老数据升级到 v2：补齐 sources / published_at / deadline_basis / event_key。

    老版本把"消息发送时间"塞进了 start_time，所以这里把 published_at 设成那个值，
    start_at 置空——宁可显示"开始时间未写明"，也不拿发布时间冒充开始时间。
    """
    data = load_todos()
    if data.get("schema_version") == SCHEMA_VERSION:
        return 0

    todos = data.get("todos") or []
    changed = 0
    for t in todos:
        dirty = False
        if not isinstance(t.get("sources"), list) or not t.get("sources"):
            t["sources"] = [{
                "group": t.get("group") or "",
                "group_id": None,
                "sender": t.get("sender") or "",
                "msg_id": t.get("source_msg_id"),
                "time": t.get("start_time"),
                "quote": t.get("source_quote"),
                "confidence": "legacy",
            }]
            dirty = True
        if "published_at" not in t:
            t["published_at"] = t.get("start_time") or t.get("created")
            dirty = True
        if "start_at" not in t:
            t["start_at"] = None
            dirty = True
        if "deadline_basis" not in t:
            t["deadline_basis"] = "unknown" if t.get("deadline") else "none"
            dirty = True
        if "deadline_raw" not in t:
            t["deadline_raw"] = None
            dirty = True
        if "event_key" not in t or not t.get("event_key"):
            t["event_key"] = event_key(t.get("title"), t.get("deadline"))
            dirty = True
        if dirty:
            changed += 1

    data["todos"] = todos
    data["schema_version"] = SCHEMA_VERSION
    save_json(TODOS_PATH, data)
    log("数据升级到 v%d：处理了 %d 条历史待办。" % (SCHEMA_VERSION, changed))
    return changed



def record_seen(messages):
    seen = load_seen()
    ids = set(seen.get("msg_ids", []))
    for m in messages:
        ids.add(m["msg_id"])
    seen["msg_ids"] = sorted(ids)
    save_json(SEEN_PATH, seen)


def public_todo(t):
    sources = t.get("sources") or []
    start = t.get("start_at") or t.get("start_time")
    return {
        "id": t.get("id"),
        "title": t.get("title"),
        "start_time": start,
        "start_at": t.get("start_at"),
        "published_at": t.get("published_at") or t.get("created"),
        "deadline": t.get("deadline"),
        "deadline_basis": t.get("deadline_basis") or ("unknown" if t.get("deadline") else "none"),
        "deadline_raw": t.get("deadline_raw"),
        "detail": t.get("detail"),
        "group": t.get("group") or "",
        "sender": t.get("sender") or "",
        "sources": sources,
        "source_count": len(sources),
        "source_confidence": (sources[0].get("confidence") if sources else None),
        "source_quote": t.get("source_quote"),
        "event_key": t.get("event_key"),
        "done": bool(t.get("done")),
        "created": t.get("created"),
    }


def public_status():
    return {
        "napcat_ok": STATE["napcat_ok"],
        "syncing": STATE["syncing"],
        "last_sync": STATE["last_sync"],
        "last_ok_sync": STATE["last_ok_sync"],
        "last_result": STATE["last_result"],
        "last_error": STATE["last_error"],
        "started_at": STATE["started_at"],
        "poll_interval": STATE["poll_interval"],
        "now": now_str(),
    }


def sync_once():
    if not SYNC_LOCK.acquire(blocking=False):
        return
    STATE["syncing"] = True
    STATE["last_error"] = None
    try:
        if not napcat_ready():
            STATE["napcat_ok"] = False
            STATE["last_result"] = "NapCat 未连接，看板仍可查看已有待办"
            log("跳过同步：NapCat 未连接", "warn")
            return

        log("开始拉取群消息…")
        new_messages, err = collect_new_messages()
        if err:
            STATE["last_error"] = err
            STATE["last_result"] = err
            log(err, "error")
            return

        log("发现 %d 条新消息。" % len(new_messages))
        if not new_messages:
            STATE["last_sync"] = now_str()
            STATE["last_ok_sync"] = STATE["last_sync"]
            STATE["last_result"] = "没有新消息"
            return

        log("交给 DeepSeek 提取待办…")
        todos = extract_todos(new_messages)
        record_seen(new_messages)
        if todos is None:
            STATE["last_error"] = "AI 提取失败"
            STATE["last_result"] = "提取失败，已记下这些消息，避免反复发送"
            log(STATE["last_result"], "error")
            return

        added = merge_todos(todos, new_messages)
        STATE["last_sync"] = now_str()
        STATE["last_ok_sync"] = STATE["last_sync"]
        STATE["last_result"] = "新增 %d 条待办（AI 检出 %d 条）" % (added, len(todos))
        log(STATE["last_result"])
        for t in todos:
            log("  · %s" % t.get("title"))
    except Exception as e:
        STATE["last_error"] = str(e)
        STATE["last_result"] = "同步出错"
        log("同步出错：%s" % e, "error")
    finally:
        STATE["syncing"] = False
        SYNC_LOCK.release()


def poll_loop():
    """同步线程：只在 NapCat 在线时按 poll_interval_seconds 拉消息，掉线时不空转、不阻塞。"""
    last_run = 0.0
    while True:
        try:
            cfg = reload_config()
            interval = max(30, int(cfg.get("poll_interval_seconds") or 180))
            STATE["poll_interval"] = interval
            if not STATE["napcat_ok"]:
                time.sleep(10)
                continue
            if time.time() - last_run >= interval:
                sync_once()
                last_run = time.time()
            time.sleep(5)
        except Exception as e:
            log("同步线程异常：%s" % e, "error")
            time.sleep(15)


def mask_secret(value):
    """回显给前端时只露头尾，别把完整 Key 发到浏览器。"""
    value = str(value or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "已填写（****）"
    return value[:3] + "…" + value[-4:]


CONFIG_EDITABLE = (
    "deepseek_api_key", "deepseek_base_url", "deepseek_model",
    "napcat_base_url", "napcat_access_token", "napcat_qq_uin", "napcat_exe",
    "target_groups", "board_port", "poll_interval_seconds", "history_count",
)


def public_config():
    cfg = reload_config()
    key = api_key(cfg)
    return {
        "has_key": bool(key),
        "key_masked": mask_secret((cfg.get("deepseek_api_key") or "").strip()),
        "key_from_env": bool((os.environ.get("DEEPSEEK_API_KEY") or "").strip()),
        "deepseek_base_url": cfg.get("deepseek_base_url", "https://api.deepseek.com"),
        "deepseek_model": cfg.get("deepseek_model", "deepseek-chat"),
        "napcat_base_url": cfg.get("napcat_base_url", "http://127.0.0.1:3000"),
        "napcat_qq_uin": str(cfg.get("napcat_qq_uin") or ""),
        "napcat_exe": cfg.get("napcat_exe", ""),
        "napcat_token_set": bool((cfg.get("napcat_access_token") or "").strip()),
        "napcat_ok": bool(STATE.get("napcat_ok")),
        "target_groups": cfg.get("target_groups") or [],
        "board_port": int(cfg.get("board_port") or 8080),
        "data_dir": DATA_DIR,
        "exe_found": find_napcat_exe(cfg),
    }


def save_config_patch(patch):
    cfg = reload_config()
    changed = []
    for field in CONFIG_EDITABLE:
        if field not in patch:
            continue
        value = patch[field]
        if field in ("deepseek_api_key", "napcat_access_token"):
            value = str(value or "").strip()
            if not value or "…" in value or "****" in value:
                continue          # 空值 / 掩码回显 一律不覆盖
        elif field == "target_groups":
            value = [int(x) for x in (value or []) if str(x).strip().isdigit()]
        elif field in ("board_port", "poll_interval_seconds", "history_count"):
            try:
                value = int(value)
            except Exception:
                continue
        else:
            value = str(value or "").strip()
        cfg[field] = value
        changed.append(field)
    save_json(CONFIG_PATH, cfg)
    return changed


def test_deepseek(patch_key=None):
    cfg = reload_config()
    key = (patch_key or "").strip() or api_key(cfg)
    if not key:
        return {"ok": False, "message": "还没填 API Key"}
    try:
        resp = requests.post(
            str(cfg.get("deepseek_base_url", "https://api.deepseek.com")).rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json={"model": cfg.get("deepseek_model", "deepseek-chat"),
                  "messages": [{"role": "user", "content": "回复一个字：通"}],
                  "max_tokens": 8, "stream": False},
            timeout=25,
        )
    except Exception as e:
        return {"ok": False, "message": "连不上 DeepSeek：%s" % str(e)[:120]}
    if resp.status_code == 200:
        try:
            model = resp.json().get("model") or cfg.get("deepseek_model")
        except Exception:
            model = cfg.get("deepseek_model")
        return {"ok": True, "message": "可用，模型 %s 正常回话" % model}
    detail = ""
    try:
        detail = (resp.json().get("error") or {}).get("message") or ""
    except Exception:
        detail = (resp.text or "")[:120]
    hint = {401: "Key 不对或已失效", 402: "账户余额不足，去 platform.deepseek.com 充值",
            429: "请求太频繁，稍后再试"}.get(resp.status_code, "HTTP %s" % resp.status_code)
    return {"ok": False, "message": "%s%s" % (hint, ("：" + detail) if detail else "")}


def test_napcat():
    data = napcat("get_login_info", {}, timeout=6)
    if not data:
        return {"ok": False, "message": "连不上 NapCat：确认它已登录，且 base_url / token 填对"}
    uin = data.get("user_id") or data.get("uin") or ""
    nick = data.get("nickname") or ""
    return {"ok": True, "message": "已连接，账号 %s%s" % (uin, ("（" + nick + "）") if nick else "")}


class BoardHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def _page(self, name):
        html_path = os.path.join(WEB_DIR, name)
        if not os.path.exists(html_path):
            self._json({"error": "缺少 web/%s" % name}, 500)
            return
        with open(html_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        if path in ("/", "/index.html", ""):
            # 首次使用没有 Key 时，直接把看板让位给配置向导（?skip=1 可跳过）
            if need_setup() and "skip=1" not in query:
                self._redirect("/setup")
                return
            self._page("index.html")
        elif path in ("/setup", "/setup.html"):
            self._page("setup.html")
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif path.startswith("/api/config"):
            self._json(public_config())
        elif path.startswith("/api/napcat/scan"):
            found = _scan_napcat()
            self._json({"candidates": found[:8], "count": len(found)})
        elif path.startswith("/api/todos"):
            data = load_todos()
            self._json({
                "todos": [public_todo(t) for t in data.get("todos") or []],
                "status": public_status(),
            })
        elif self.path.startswith("/api/status"):
            self._json(public_status())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        body = self._read_body()
        if self.path == "/api/todo/done":
            self._set_done(body.get("id"), True)
        elif self.path == "/api/todo/undo":
            self._set_done(body.get("id"), False)
        elif self.path == "/api/todo/delete":
            self._delete(body.get("id"))
        elif self.path == "/api/todo/ignore":
            self._ignore(body.get("id"))
        elif self.path == "/api/sync":
            if STATE["syncing"]:
                self._json({"ok": True, "status": public_status()})
                return
            threading.Thread(target=sync_once, daemon=True).start()
            self._json({"ok": True, "status": public_status()})
        elif self.path == "/api/config":
            before_port = int(reload_config().get("board_port") or 8080)
            changed = save_config_patch(body)
            after_port = int(reload_config().get("board_port") or 8080)
            self._json({
                "ok": True,
                "changed": changed,
                "restart_needed": bool("board_port" in changed and before_port != after_port),
                "config": public_config(),
            })
        elif self.path == "/api/config/test":
            target = (body.get("target") or "").strip()
            if target == "deepseek":
                result = test_deepseek(body.get("deepseek_api_key"))
            elif target == "napcat":
                result = test_napcat()
            else:
                result = {"ok": False, "message": "target 只能是 deepseek 或 napcat"}
            self._json(result)
        else:
            self._json({"error": "not found"}, 404)

    def _set_done(self, tid, done):
        data = load_todos()
        for t in data["todos"]:
            if t.get("id") == tid:
                t["done"] = done
                break
        save_json(TODOS_PATH, data)
        self._json({"ok": True})

    def _delete(self, tid):
        data = load_todos()
        data["todos"] = [t for t in data["todos"] if t.get("id") != tid]
        save_json(TODOS_PATH, data)
        self._json({"ok": True})

    def _ignore(self, tid):
        data = load_todos()
        target = None
        kept = []
        for t in data["todos"]:
            if t.get("id") == tid:
                target = t
            else:
                kept.append(t)
        data["todos"] = kept
        save_json(TODOS_PATH, data)

        if target:
            kw = target.get("title") or ""
            kw = re.sub(r"[\s，。,.!！?？、；;：:()（）\-—_]+", "", kw)[:12]
            if len(kw) >= 2:
                ignores = load_ignores()
                kws = [str(k) for k in ignores.get("keywords", [])]
                if kw not in kws:
                    kws.append(kw)
                    ignores["keywords"] = kws
                    save_json(IGNORE_PATH, ignores)
            msg_ids = [target.get("source_msg_id")]
            msg_ids += [s.get("msg_id") for s in (target.get("sources") or [])]
            msg_ids = [str(x) for x in msg_ids if x]
            if msg_ids:
                seen = load_seen()
                ignored = set(seen.get("ignored_msg_ids", [])) | set(msg_ids)
                seen["ignored_msg_ids"] = sorted(ignored)
                save_json(SEEN_PATH, seen)
        self._json({"ok": True})


def start_server(port, open_browser=True):
    server = ThreadingHTTPServer(("127.0.0.1", port), BoardHandler)
    url = "http://127.0.0.1:%d" % port
    log("看板已就绪：%s" % url)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    server.serve_forever()


def board_already_running(port):
    """端口上已经跑着本程序（而不是别的服务）时，不要重复启动。"""
    try:
        resp = requests.get("http://127.0.0.1:%d/api/status" % port, timeout=2)
        data = resp.json()
        return isinstance(data, dict) and "napcat_ok" in data and "last_result" in data
    except Exception:
        return False


def parse_args(argv):
    mode = "run"
    port = None
    background = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("run", "once", "serve", "daemon"):
            mode = "run" if arg == "daemon" else arg
            background = background or arg == "daemon"
        elif arg == "--background":
            background = True
        elif arg == "--port" and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                pass
            i += 1
        elif arg.startswith("--port="):
            try:
                port = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        i += 1
    if port is None:
        env_port = (os.environ.get("QQTODO_BOARD_PORT") or "").strip()
        if env_port.isdigit():
            port = int(env_port)
    return mode, port, background


def main():
    global CONFIG
    CONFIG = reload_config()
    mode, cli_port, background = parse_args(sys.argv[1:])
    port = cli_port or int(CONFIG.get("board_port") or 8080)
    open_browser = bool(CONFIG.get("auto_open_browser", True)) and not background

    log("=" * 46)
    log("QQ 待办助手启动：模式 %s，端口 %d%s" % (mode, port, "，后台运行" if background else ""))
    log("=" * 46)

    if board_already_running(port):
        log("检测到看板已在 http://127.0.0.1:%d 运行，本次启动退出。" % port)
        if not background:
            webbrowser.open("http://127.0.0.1:%d" % port)
        return

    STATE["started_at"] = now_str()
    ensure_schema()
    dedupe_existing()

    if mode == "serve":
        start_server(port, open_browser)
        return

    threading.Thread(target=napcat_supervisor, daemon=True).start()

    if mode == "once":
        timeout = int(CONFIG.get("napcat_wait_seconds") or 60)
        log("等待 NapCat 就绪（最多 %d 秒）…" % timeout)
        deadline = time.time() + timeout
        while time.time() < deadline and not STATE["napcat_ok"]:
            time.sleep(2)
        sync_once()
        start_server(port, open_browser)
        return

    threading.Thread(target=poll_loop, daemon=True).start()
    log("常驻模式：看板常开，NapCat 掉线会自动重连。")
    start_server(port, open_browser)


if __name__ == "__main__":
    main()
