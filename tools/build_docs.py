# -*- coding: utf-8 -*-
"""生成《QQ 待办助手》两份 PDF：产品使用手册 + 产品说明书。

用法：
    python tools/build_docs.py

产物：
    docs/手册与说明书/QQ待办助手-使用手册.pdf
    docs/手册与说明书/QQ待办助手-产品说明书.pdf
"""
import os

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(BASE, "docs", "screenshots")
DIAG = os.path.join(BASE, "docs", "diagrams")
OUT_DIR = os.path.join(BASE, "docs", "手册与说明书")

# ---------------------------------------------------------------- 字体
FONT = "YaHei"
BOLD = "YaHei-Bold"
pdfmetrics.registerFont(TTFont(FONT, r"C:\Windows\Fonts\msyh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont(BOLD, r"C:\Windows\Fonts\msyhbd.ttc", subfontIndex=0))
pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=BOLD, italic=FONT, boldItalic=BOLD)

# ---------------------------------------------------------------- 配色
PRIMARY = colors.HexColor("#0F766E")
PRIMARY_DK = colors.HexColor("#115E59")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#E2E8F0")
SOFT = colors.HexColor("#F5F7F9")
SOFT_TEAL = colors.HexColor("#EAF4F2")
WARN_BG = colors.HexColor("#FDF6EC")
WARN_LINE = colors.HexColor("#D97706")

PAGE_W, PAGE_H = A4
ML = MR = 56
MT, MB = 62, 58
CONTENT_W = PAGE_W - ML - MR

# ---------------------------------------------------------------- 样式
_F = dict(fontName=FONT, fontSize=10.5, leading=18, textColor=INK, alignment=TA_LEFT)
S = {
    "body": ParagraphStyle("body", **_F),
    "body_tight": ParagraphStyle("bt", **dict(_F, leading=16.5)),
    "lead": ParagraphStyle("lead", **dict(_F, fontSize=11.6, leading=20,
                                          textColor=colors.HexColor("#334155"))),
    "h1": ParagraphStyle("H1", **dict(_F, fontName=BOLD, fontSize=19, leading=25,
                                      textColor=PRIMARY_DK, spaceBefore=4, spaceAfter=8)),
    "h2": ParagraphStyle("H2", **dict(_F, fontName=BOLD, fontSize=13.2, leading=19,
                                      textColor=INK, spaceBefore=12, spaceAfter=5)),
    "h3": ParagraphStyle("H3", **dict(_F, fontName=BOLD, fontSize=11, leading=17,
                                      textColor=PRIMARY_DK, spaceBefore=8, spaceAfter=3)),
    "bullet": ParagraphStyle("bullet", **dict(_F, leading=17, leftIndent=16, bulletIndent=2)),
    "small": ParagraphStyle("small", **dict(_F, fontSize=9, leading=14, textColor=MUTED)),
    "cap": ParagraphStyle("cap", **dict(_F, fontSize=8.6, leading=13, textColor=MUTED,
                                        alignment=TA_CENTER)),
    "th": ParagraphStyle("th", **dict(_F, fontName=BOLD, fontSize=9.3, leading=13.5,
                                      textColor=colors.white)),
    "td": ParagraphStyle("td", **dict(_F, fontSize=9.2, leading=13.5)),
    "code": ParagraphStyle("code", **dict(_F, fontName=FONT, fontSize=8.8, leading=14.5,
                                          textColor=colors.HexColor("#E2E8F0"))),
    "toc0": ParagraphStyle("toc0", **dict(_F, fontName=BOLD, fontSize=9.8, leading=17.5,
                                          spaceBefore=1)),
    "toc1": ParagraphStyle("toc1", **dict(_F, fontSize=8.8, leading=13.2, textColor=MUTED,
                                          leftIndent=18)),
}


# ---------------------------------------------------------------- 组件
def H1(text):
    p = Paragraph(text, S["h1"])
    p._toc = (0, text)
    return p


def H2(text):
    p = Paragraph(text, S["h2"])
    p._toc = (1, text)
    return p


def P(text, style="body"):
    return Paragraph(text, S[style])


def BUL(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def NUM(items):
    return [Paragraph(t, S["bullet"], bulletText="%d." % i) for i, t in enumerate(items, 1)]


def gap(h=8):
    return Spacer(1, h)


def rule(color=LINE, width=CONTENT_W, thickness=0.7):
    t = Table([[""]], colWidths=[width], rowHeights=[1])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), thickness, color),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def code_block(lines, width=CONTENT_W):
    cells = [[Paragraph(l.replace(" ", "&nbsp;").replace("<", "&lt;") or "&nbsp;",
                        S["code"])] for l in lines]
    t = Table(cells, colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t


def callout(text, kind="note", title=None):
    if kind == "warn":
        bg, bar, head = WARN_BG, WARN_LINE, "注意"
    else:
        bg, bar, head = SOFT_TEAL, PRIMARY, "说明"
    body = ('<font name="%s" color="#115E59">%s　</font>' % (BOLD, title or head)) + text
    t = Table([[Paragraph(body, P("", "body").style)]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t


def table(rows, widths, header=True):
    data = []
    for r, row in enumerate(rows):
        line = []
        for cell in row:
            style = S["th"] if (header and r == 0) else S["td"]
            line.append(Paragraph(str(cell), style))
        data.append(line)
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                 ("TOPPADDING", (0, 0), (-1, 0), 8),
                 ("BOTTOMPADDING", (0, 0), (-1, 0), 8)]
        for i in range(1, len(data)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), SOFT))
    t.setStyle(TableStyle(cmds))
    return t


def scenario(pairs):
    """场景三段式：输入 / 处理 / 价值，用两列表格排，标签与正文对齐更整齐。"""
    rows = [[Paragraph("<b>%s</b>" % k, S["td"]), Paragraph(v, S["body_tight"])]
            for k, v in pairs]
    t = Table(rows, colWidths=[58, CONTENT_W - 58], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
    ]))
    return t


def figure(path, width=CONTENT_W, caption=None, max_h=320):
    with PILImage.open(path) as im:
        w, h = im.size
    height = width * h / w
    if height > max_h:
        height = max_h
        width = height * w / h
    flow = Image(path, width=width, height=height)
    flow.hAlign = "CENTER"
    if not caption:
        return flow
    return KeepTogether([flow, gap(3), Paragraph(caption, S["cap"])])


# ---------------------------------------------------------------- 文档骨架
class Doc(BaseDocTemplate):
    def __init__(self, path, title, footer_title, cover_data):
        super().__init__(path, pagesize=A4, leftMargin=ML, rightMargin=MR,
                         topMargin=MT, bottomMargin=MB, title=title,
                         author="QQ 待办助手", subject=footer_title)
        self.footer_title = footer_title
        self.cover_data = cover_data
        frame_cover = Frame(0, 0, PAGE_W, PAGE_H, id="cover", leftPadding=0, rightPadding=0,
                            topPadding=0, bottomPadding=0, showBoundary=0)
        frame_body = Frame(ML, MB, CONTENT_W, PAGE_H - MT - MB, id="body",
                           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame_cover], onPage=self.draw_cover),
            PageTemplate(id="body", frames=[frame_body], onPage=self.draw_body),
        ])
        self._bm = 0

    # ---- 封面：整页用 canvas 画，story 里只留一个分页
    def draw_cover(self, canv, doc):
        d = self.cover_data
        canv.saveState()
        canv.setFillColor(PRIMARY)
        canv.rect(0, PAGE_H - 400, PAGE_W, 400, stroke=0, fill=1)
        canv.setFillColor(PRIMARY_DK)
        canv.rect(0, PAGE_H - 400, PAGE_W, 7, stroke=0, fill=1)

        canv.setFillColor(colors.HexColor("#A7D9D2"))
        canv.setFont(FONT, 9.6)
        canv.drawString(ML, PAGE_H - 78, d["kicker"])

        canv.setFillColor(colors.white)
        canv.setFont(BOLD, 33)
        canv.drawString(ML, PAGE_H - 160, d["title"])
        canv.setFillColor(colors.HexColor("#CFEAE5"))
        canv.setFont(FONT, 14.5)
        canv.drawString(ML, PAGE_H - 196, d["tagline"])

        canv.setStrokeColor(colors.HexColor("#3E9F94"))
        canv.setLineWidth(1)
        canv.line(ML, PAGE_H - 240, ML + 90, PAGE_H - 240)

        canv.setFillColor(colors.white)
        canv.setFont(BOLD, 21)
        canv.drawString(ML, PAGE_H - 292, d["subtitle"])
        canv.setFillColor(colors.HexColor("#BFE3DD"))
        canv.setFont(FONT, 10.4)
        y = PAGE_H - 322
        for line in d.get("sub_lines", []):
            canv.drawString(ML, y, line)
            y -= 17

        canv.setFillColor(MUTED)
        canv.setFont(FONT, 8.6)
        canv.drawString(ML, 34, d["footer"])

        # 下半部分：元信息 + 截图
        y = PAGE_H - 452
        canv.setFont(BOLD, 9.5)
        canv.setFillColor(INK)
        for k, v in d["meta"]:
            canv.setFillColor(MUTED)
            canv.setFont(FONT, 8.8)
            canv.drawString(ML, y, k)
            canv.setFillColor(INK)
            canv.setFont(FONT, 10.2)
            canv.drawString(ML + 96, y, v)
            canv.setStrokeColor(LINE)
            canv.setLineWidth(0.5)
            canv.line(ML, y - 7, PAGE_W - MR, y - 7)
            y -= 24

        shot = d.get("shot")
        if shot and os.path.exists(shot):
            with PILImage.open(shot) as im:
                w, h = im.size
            max_w = PAGE_W - 2 * ML - 30
            max_h = y - 60
            iw = min(max_w, max_h * w / h)
            ih = iw * h / w
            canv.drawImage(shot, (PAGE_W - iw) / 2, 74, width=iw, height=ih, mask="auto")
        canv.restoreState()

    def draw_body(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(LINE)
        canv.setLineWidth(0.7)
        canv.line(ML, PAGE_H - 40, PAGE_W - MR, PAGE_H - 40)
        canv.setFont(FONT, 8.4)
        canv.setFillColor(MUTED)
        canv.drawString(ML, PAGE_H - 34, self.footer_title)
        canv.drawRightString(PAGE_W - MR, PAGE_H - 34, "QQ 待办助手")
        canv.line(ML, 42, PAGE_W - MR, 42)
        canv.setFont(FONT, 8.6)
        canv.drawCentredString(PAGE_W / 2, 27, "— %d —" % doc.page)
        canv.restoreState()

    def beforeDocument(self):
        # multiBuild 会多次排版，每轮都要重置书签计数，否则 TOC 永远无法收敛
        self._bm = 0

    def afterFlowable(self, flowable):
        info = getattr(flowable, "_toc", None)
        if not info:
            return
        level, text = info
        self._bm += 1
        k = "sec%d" % self._bm
        self.canv.bookmarkPage(k)
        self.canv.addOutlineEntry(text, k, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, k))


def cover_flow(cover_data):
    return [NextPageTemplate("body"), PageBreak()]


def quickstart():
    """目录页剩余空间放一张速查表，避免半页空白。"""
    out = [gap(14), rule(PRIMARY, thickness=1.2), gap(10),
           Paragraph("30 分钟上手（速查）", S["h2"]), gap(2)]
    out += [table([
        ["步骤", "做什么", "关键动作"],
        ["1", "装 Python", "python.org 下载，勾选 Add python.exe to PATH"],
        ["2", "装 NapCat 并扫码登录一次", "记下 OneBot 端口与 token，记下 NapCatWinBootMain.exe 路径"],
        ["3", "一键安装本程序", "powershell -ExecutionPolicy Bypass -File install.ps1"],
        ["4", "打开 http://127.0.0.1:8080", "没填 Key 会自动进配置向导，填完点“保存并进入看板”"],
        ["5", "每天打开看板", "点方框=完成；详情里“这不是待办”=教它别再提醒"],
    ], [40, 180, 263])]
    out += [gap(8), callout("三个最容易踩的坑：<b>Python 没进 PATH</b>（命令找不到）、"
                            "<b>NapCat 没在登录态</b>（状态一直“未连接”）、"
                            "<b>Key 前多了空格</b>（测试报 Authentication Fails）。", "warn", "速查提示")]
    return out


def digest():
    """说明书用：目录页剩余空间放“一页读完全文”。"""
    out = [gap(14), rule(PRIMARY, thickness=1.2), gap(10),
           Paragraph("一页读完全文", S["h2"]), gap(2)]
    out += [table([
        ["看什么", "一句话结论", "详见"],
        ["要解决的问题", "高校信息集中在 QQ 群，漏、复、糊三件事靠人肉记不住", "1.2"],
        ["产品形态", "本地优先的单机工具：NapCat 接入 + AI 提炼 + 网页看板", "1.1 / 5.1"],
        ["与同类差别", "模型只做语言理解，时间换算与去重交给代码，结论可回溯到原文", "4.1 / 4.3"],
        ["技术骨架", "Python 标准库 + 一个 requests；JSON 持久化；计划任务常驻 + 看门狗自愈", "5.2 / 5.4"],
        ["边界与风险", "需电脑常开、依赖非官方 NapCat、暂无多人与手机直连", "2.3 / 7"],
    ], [90, 315, 78])]
    out += [gap(8), callout("本说明书所有截图与示例数据均为<b>编造内容</b>，不含任何真实群名、同学昵称与密钥。")]
    return out


def toc_flow(title="目　录", panel=None):
    out = [Paragraph(title, S["h1"]), gap(2), rule()]
    toc = TableOfContents()
    toc.levelStyles = [S["toc0"], S["toc1"]]
    toc.dotsMinLevel = 0
    out += [gap(8), toc]
    out += panel if panel is not None else quickstart()
    out += [PageBreak()]
    return out


def build(path, story, title, footer_title, cover_data):
    doc = Doc(path, title, footer_title, cover_data)
    doc.multiBuild(story)
    return path


# ================================================================ 使用手册
def manual_story():
    s = []
    s += [H1("1　关于本手册"), P(
        "这份手册写给第一次接触 QQ 待办助手的人。读完它，你应该能独立完成三件事："
        "把程序装在自己的电脑上、把配置填对、看懂并会用那张待办看板。"
        "手册里的每一步都对应真实界面，出现问题的分支也写了怎么排查。", "lead"), gap(6)]

    s += [H2("1.1　适用对象与阅读顺序")]
    s += [table([
        ["你是谁", "建议先看", "大概需要"],
        ["完全没写过代码，只想用起来", "第 3 章 → 第 5 章 → 第 6 章", "30 分钟"],
        ["会基本命令，想改配置、改端口", "第 5 章 → 第 8 章 → 附录 A", "20 分钟"],
        ["想改代码、接自己的模型或前端", "第 6 章 → 附录 B → README 的开发说明", "—"],
    ], [168, 205, 110])]

    s += [gap(8), H2("1.2　排版约定")]
    s += BUL([
        "深色底块里是<b>可以直接复制执行的命令</b>，按顺序粘贴到 PowerShell 窗口即可。",
        "带竖线的浅色方块是说明，橙色方块是需要特别留意的风险或易错点。",
        "“界面文字”用引号标出，例如点“保存并进入看板”，都是为了让你能对着界面找到同一个按钮。",
        "第 5 章之后出现的接口、字段名（如 <font name='YaHei-Bold'>deadline_basis</font>）是给愿意深入的人看的，普通使用可以跳过。",
    ])

    s += [gap(6), H2("1.3　一句话原理")]
    s += [P("程序做四件事：<b>读</b>你 QQ 群里新来的消息，<b>问</b>一次大模型“这里面有没有需要我动手的事”，"
           "把答案<b>清洗合并</b>成不重复的条目，最后用一张<b>网页看板</b>展示出来。"
           "整个过程在你自己的电脑上完成，QQ 消息只有交给模型提炼时才会离开本机。"), gap(4)]
    s += [callout("大模型只负责“看懂人话”，时间换算、去重、合并这些容易算错的部分全部由代码完成。"
                  "这条分工是本项目准确率的主要来源，详见《产品说明书》第 4 章。")]

    # ---------------------------------------------------------------- 2
    s += [PageBreak(), H1("2　它替你做什么"),
          P("班级群、年级群、社团群、课程群，一天下来几十上百条。真正需要你动手的，往往只有三五条："
            "交表、报名、签到、领书、开会。剩下的都是“收到”“谢谢老师”和别人的闲聊。"
            "人肉翻群的问题不是看不到，而是<b>看到了又忘</b>。", "lead"), gap(6)]

    s += [H2("2.1　三件具体的事")]
    s += BUL([
        "<b>从噪音里挑出任务</b>：一条通知里如果有“提交、填写、报名、截止、扫码进群”这类要求，它会被提炼成一条待办；纯通知、纯闲聊、纯表情不算。",
        "<b>把重复的合成一条</b>：同一份通知被三个群转发，看板上仍然只有一张卡片，卡片下面写着“另有 2 处来源”。",
        "<b>把时间说清楚</b>：原文说“今晚9点前”，看板上写“今天 21:00 还剩 3 小时”，并标注这是“按原文推算”，原始说法保留在详情里可追溯。",
    ])

    s += [gap(6), H2("2.2　和你现在的做法比")]
    s += [table([
        ["做法", "能不能不漏", "会不会重复", "时间清不清楚", "要不要一直盯着"],
        ["人肉翻群", "状态好才行", "不会，但要自己记", "靠脑子换算，容易错", "要，而且随时"],
        ["群待办/群公告类小程序", "只覆盖点了“待办”的那条", "多个群各存一份", "多半不解析", "不用，但覆盖不全"],
        ["本项目", "每 3 分钟扫一次，新消息不漏", "自动合并成一条并保留来源", "自动换算并标注依据", "不用，打开网页就有"],
    ], [120, 97, 92, 96, 78])]

    s += [gap(8), callout("本项目不是“云服务”，它是装在你电脑上的一个小程序：数据存在本地 JSON 文件里，"
                          "所以断网时看板照样能打开（只是不会刷新新消息）。这也是它和个人信息保护友好的地方。")]

    # ---------------------------------------------------------------- 3
    s += [PageBreak(), H1("3　开始之前"),
          P("先把要准备的东西摆齐，再动手安装，能少走很多弯路。", "lead"), gap(6)]

    s += [H2("3.1　清单")]
    s += [table([
        ["需要什么", "说明", "必需吗"],
        ["一台 Windows 电脑", "Windows 10 / 11。程序用计划任务做自启，其他系统要自己改启动方式", "必需"],
        ["Python 3.9 及以上", "建议 3.10+；安装时务必勾选 Add Python to PATH", "必需"],
        ["一个 QQ 号", "用于登录 NapCat 读取群消息；建议先用小号试", "必需"],
        ["NapCat（QQ 自动化框架）", "开源项目，负责把 QQ 群消息变成 HTTP 接口", "必需"],
        ["DeepSeek API Key", "在 platform.deepseek.com 创建，按量计费", "必需"],
        ["可用的网络", "提炼时要访问 DeepSeek 接口；断网时程序会跳过本次同步", "必需"],
    ], [140, 268, 75])]

    s += [gap(8), H2("3.2　必须知道的风险")]
    s += [callout("<b>NapCat 属于非官方 QQ 客户端框架</b>，用它登录 QQ 存在被平台判定为异常登录、进而限制账号的风险。"
                  "多数人长期使用没有出问题，但风险客观存在，不能承诺为零。"
                  "建议<b>先用一个小号</b>跑一周，确认稳定后再考虑换成常用号；不要用这个号做任何涉及资金的操作。", "warn")]

    s += [gap(4), callout("DeepSeek 按 token 计费。按本项目默认节奏（每 3 分钟扫一次、只在新消息时调用模型），"
                          "每天大约 1.5 万输入 token、2 千输出 token，折合约 <b>0.05 元／天、1.4 元／月</b>；"
                          "一年不到 17 元。具体价格以官方价目为准，可在平台后台设置余额提醒。", "note", "费用")]

    s += [gap(4), callout("程序需要你的电脑处于开机状态才能抓消息。关机期间群里的消息抓不到，开机后会补拉 NapCat 历史记录范围内的消息"
                          "（默认每群最近 50 条）。想 24 小时在线，需要一台常开的机器或云服务器。", "note", "在线时间")]

    # ---------------------------------------------------------------- 4
    s += [PageBreak(), H1("4　安装（三步，约 15 分钟）")]

    s += [H2("4.1　装 Python")]
    s += NUM([
        "打开 python.org/downloads 下载 Windows 安装包（64-bit）。",
        "双击安装，第一页底部<b>勾选 “Add python.exe to PATH”</b>，再点 Install Now。这一步漏了，后面所有命令都会提示找不到 python。",
        "装完打开“终端 / PowerShell”，输入下面这行，能看到版本号就成功。",
    ])
    s += [code_block(["python --version", "# 期望输出：Python 3.12.x（3.9 以上都行）"])]

    s += [gap(6), H2("4.2　装 NapCat 并登录一次")]
    s += NUM([
        "到 github.com/NapNeko/NapCatQQ/releases 下载 Windows 版（Shell 或 OneKey 一键包）。",
        "解压后双击启动，会弹出内置的 QQ 登录窗口，<b>扫码登录一次</b>。这一次必须手动扫，之后才能免扫码。",
        "登录成功后，NapCat 会起一个本地 OneBot v11 HTTP 服务。在它的 WebUI / 配置里确认三件事：<b>监听端口</b>（常见 3000 或 6099）、"
        "<b>access_token</b>（有就记下，没有就留空）、HTTP 服务已启用。",
        "记下 <font name='YaHei-Bold'>NapCatWinBootMain.exe</font> 的完整路径。程序要靠它在你开机时把 NapCat 拉起来。",
    ])
    s += [gap(2), callout("不确定路径也没关系：配置向导里有“自动查找”，会在常见目录里帮你扫出来。")]

    s += [gap(6), H2("4.3　装本程序并注册自启")]
    s += [P("把项目放到一个<b>路径里没有中文和空格</b>的目录（例如 <font name='YaHei-Bold'>F:\\qq-todo-bot</font>），"
           "在该目录打开 PowerShell，执行：")]
    s += [code_block([
        "powershell -ExecutionPolicy Bypass -File install.ps1",
        "",
        "# 脚本会自动做四件事：",
        "# 1) 找到真实的 python.exe（绕开商店占位符）",
        "# 2) 安装依赖（只有一个 requests）",
        "# 3) 注册计划任务 QQTodoBot + 看门狗 QQTodoBot-Watchdog",
        "# 4) 立刻在后台启动，并检查看板是否响应",
    ])]
    s += [gap(8)]
    s += [P("看到 <font name='YaHei-Bold'>看板已在后台运行：http://127.0.0.1:8080</font> 就说明装好了。"
           "这个任务在你<b>登录桌面时</b>自动启动，不需要管理员权限，也不会有黑窗口。"), gap(2)]
    s += [callout("只想临时试一下、不想注册计划任务：双击项目里的 <b>start.bat</b>。"
                  "它会先探测后台服务——已经在跑就直接打开看板并退出，没跑才临时以前台方式启动（关掉窗口就停）。")]

    # ---------------------------------------------------------------- 5
    s += [PageBreak(), H1("5　首次配置向导"),
          P("这一步是整个安装里最容易卡住的地方，所以程序把它做成了一个网页。"
            "装好之后用浏览器打开 <font name='YaHei-Bold'>http://127.0.0.1:8080</font>："
            "<b>如果还没有可用的 Key，看板会自动跳到配置向导</b>，不用你去找入口。", "lead"), gap(6)]

    s += [figure(os.path.join(SHOT, "board-list.png"), width=CONTENT_W,
                 caption="图 1　待办看板：左边是范围与群筛选，中间按“已逾期／今天／本周内／没写截止”分组", max_h=250)]

    s += [gap(10), H2("5.1　三步填完")]
    s += NUM([
        "<b>填 DeepSeek Key</b>：粘贴 sk- 开头的那串，点旁边的“测试”。出现“可用，模型正常回话”才算通过。",
        "<b>填 NapCat</b>：填 OneBot 地址（默认 http://127.0.0.1:3000）、token、QQ 号；路径不确定就点“自动查找”，再点“测试连接”。",
        "<b>点“保存并进入看板”</b>。保存后<b>立即生效，不需要重启</b>；只有改看板端口才需要重启服务。",
    ])
    s += [gap(2), callout("想先看看长什么样、暂时不填 Key：点向导页上的“直接进入看板”，"
                          "或访问 <b>/?skip=1</b>。此时看板能看历史待办，但不会同步新消息。")]

    s += [gap(6), H2("5.2　测试按钮会说什么")]
    s += [table([
        ["提示文案", "真实含义", "怎么办"],
        ["可用，模型 deepseek-flash 正常回话", "Key 有效，模型能正常返回", "不用管，继续"],
        ["Key 不对或已失效：Authentication Fails", "Key 打错、被重置或复制时带了空格", "回平台重新复制一次，注意首尾空格"],
        ["余额不足", "账户里没钱或额度用完", "去平台充值，或换一个 Key"],
        ["请求太频繁 / 429", "短时间内调用过多", "等 1 分钟再测"],
        ["已连接，账号 xxxxx（昵称）", "NapCat 在线且鉴权通过", "继续"],
        ["连不上 NapCat / token 不对", "地址端口错、token 错、或 NapCat 没登录", "核对端口与 token；看 NapCat 窗口是否还在登录态"],
    ], [180, 168, 135])]

    s += [gap(8), H2("5.3　Key 的存放与回显")]
    s += [P("Key 只写在本机的 <font name='YaHei-Bold'>config.json</font>，不会上传到任何服务器。"
           "已保存的 Key 在界面上只露头尾（如 <font name='YaHei-Bold'>sk-…cdef</font>）："
           "留空就是“不改”，带省略号的回显不会把真实 Key 覆盖掉，不用担心点保存时把 Key 洗掉。")]
    s += [P("也支持用环境变量 <font name='YaHei-Bold'>DEEPSEEK_API_KEY</font> 提供 Key，优先级高于 config.json，"
           "适合临时环境或不方便写文件的场合。")]

    # ---------------------------------------------------------------- 6
    s += [gap(14), H1("6　看板怎么用")]

    s += [H2("6.1　三个视图")]
    s += [table([
        ["视图", "按什么排序", "什么时候用"],
        ["列表", "已逾期 → 今天 → 明天 → 本周内 → 以后 → 没写截止", "每天早上扫一眼，先干掉逾期的"],
        ["时间轴", "按具体日期往下排，同一天的排在一起", "想看“这周哪天最挤”、要不要提前准备"],
        ["日历", "月视图，格子里是当天截止的事", "安排周末、看某一天到底有什么事"],
    ], [70, 250, 163])]

    s += [gap(6), figure(os.path.join(SHOT, "board-calendar.png"), width=CONTENT_W,
                         caption="图 2　日历视图：格子里是当天截止的事项，点某一天，下方列出那天的全部待办", max_h=240)]
    s += [gap(10), figure(os.path.join(SHOT, "board-timeline.png"), width=CONTENT_W,
                          caption="图 3　时间轴视图：昨天／今天／后天／周几，一眼看出时间有多挤", max_h=240)]

    s += [PageBreak(), H2("6.2　筛选与搜索")]
    s += BUL([
        "<b>左侧范围</b>：全部待办 / 今天要做 / 已完成，三个数就是你的工作量。",
        "<b>左侧“群来源”</b>：点群名只看这个群，可以多选；某个群太吵就把它单独折进去。",
        "<b>顶部标签</b>：全部 / 已逾期 / 今天 / 本周 / 没写截止 / 来源待确认，比按天分组更直接。",
        "<b>搜索框</b>：标题、说明、群名、发送者、消息原文都能搜。",
    ])

    s += [gap(6), H2("6.3　一条待办能做的三件事")]
    s += [table([
        ["操作", "在哪儿", "结果"],
        ["标记完成", "点左侧方框，或详情里的“标记完成”", "划掉并移入“已完成”；在“已完成”里再点可恢复"],
        ["这不是待办", "详情里的按钮", "删除这条，并记住关键词和消息 ID，以后类似消息不再打扰你"],
        ["删除", "详情里的按钮", "只删这条，不教它"],
    ], [92, 190, 201])]
    s += [gap(8)]
    s += [P("点“详情”展开，能看到发送时间、原文引文、完整说明，以及“另有 N 处来源”的来源清单——"
           "哪条通知来自哪个群、谁发的、什么时候发的，都可查。")]

    s += [gap(6), H2("6.4　小技巧")]
    s += BUL([
        "按 <font name='YaHei-Bold'>/</font> 直接聚焦搜索框，按 <font name='YaHei-Bold'>Esc</font> 清空并收起侧栏。",
        "侧栏底部可切换深色模式，选择会被浏览器记住；也可以直接用 <font name='YaHei-Bold'>?theme=dark</font> 打开。",
        "深链接：<font name='YaHei-Bold'>#list</font>、<font name='YaHei-Bold'>#timeline</font>、<font name='YaHei-Bold'>#calendar</font> 可直接打开对应视图，适合存成书签。",
        "页面每 10 秒自动拉一次数据；浏览器标签页切到后台时暂停刷新，不白耗电。",
        "右上角“立即同步”可以不等 3 分钟，手动催一次。",
    ])
    s += [gap(4), callout("当前版本只监听本机地址（127.0.0.1），所以<b>手机不能直接访问</b>。"
                          "手册里的手机截图是用同一套页面缩小视口拍的，布局本身是自适应的；"
                          "真要用手机看，需要把监听地址改成 0.0.0.0（改一行代码）或做端口转发，后续版本会加开关。", "warn", "关于手机访问")]

    # ---------------------------------------------------------------- 7
    s += [PageBreak(), H1("7　教它：让待办越来越准"),
          P("模型第一次上手不可能完全懂你们班的语境。这个程序给了你一条“纠错即学习”的路径，越用越准。", "lead"), gap(6)]

    s += [table([
        ["你做的事", "程序记住什么", "下次效果"],
        ["点“这不是待办”", "标题里最长的那段关键词（最多 12 字）+ 这条消息的 ID", "再出现同样关键词的消息，直接跳过，不再问你"],
        ["点“标记完成”", "截止日期 + 任务本身", "同一件事被别的群转发时，不会又冒出来一条“没做完”"],
        ["改配置换模型", "deepseek_model 字段", "换成更强的模型，提炼更稳，费用略高"],
    ], [110, 220, 153])]

    s += [gap(6), callout("这些记忆都存在本地：忽略关键词在 <b>ignore_keywords.json</b>，已读消息 ID 在 <b>seen.json</b>。"
                          "想“重来一次”，把这两个文件删掉即可，待办数据不受影响。")]

    # ---------------------------------------------------------------- 8
    s += [PageBreak(), H1("8　日常运维（不常用，但值得存下来）")]

    s += [H2("8.1　常用命令")]
    s += [code_block([
        "# 看最近的日志（出问题先看这里）",
        "Get-Content .\\logs\\app.log -Tail 50",
        "",
        "# 看后台任务状态",
        "Get-ScheduledTask -TaskName QQTodoBot | Select-Object TaskName, State",
        "",
        "# 重启后台服务",
        "Stop-ScheduledTask -TaskName QQTodoBot; Start-ScheduledTask -TaskName QQTodoBot",
        "",
        "# 换端口（临时，优先级高于 config.json）",
        "$env:QQTODO_BOARD_PORT = 8090; python main.py serve",
    ])]

    s += [gap(8), H2("8.2　自愈是怎么工作的")]
    s += BUL([
        "计划任务 <font name='YaHei-Bold'>QQTodoBot</font> 在你登录桌面时启动 <font name='YaHei-Bold'>pythonw.exe main.py --background</font>，无窗口、不弹浏览器。",
        "另一个任务 <font name='YaHei-Bold'>QQTodoBot-Watchdog</font> 每 2 分钟探一次端口：发现看板没响应就重新拉起主任务。"
        "Windows 计划任务自带的“失败后重启”在被强杀时不会触发，真正兜底的是这一层。",
        "NapCat 掉线时，主程序按退避策略重新拉起 NapCat；<b>掉线期间看板照常显示历史待办</b>，只是不刷新。",
        "重复启动不会开出第二个进程抢端口——单实例保护。",
    ])

    s += [gap(6), H2("8.3　日志在说什么")]
    s += [table([
        ["日志片段", "含义"],
        ["看板已就绪：http://127.0.0.1:8080", "服务起来了，可以打开网页"],
        ["跳过同步：NapCat 未连接", "QQ 侧没登录或地址不对，看板仍可用"],
        ["发现 N 条新消息", "本轮真的抓到了新消息，接下来会调用模型"],
        ["没有新消息", "本轮没有新内容，没花一分钱"],
        ["新增 N 条待办（AI 检出 M 条）", "M 是模型识别数，N 是合并去重后真正入库的数量"],
        ["提取失败，已记下这些消息", "模型这次没给出可用结果，这些消息被标记已处理，不会反复重试烧钱"],
    ], [240, 243])]

    # ---------------------------------------------------------------- 9
    s += [PageBreak(), H1("9　数据、备份与迁移"),
          P("程序的数据全是普通 JSON 文件，随时可以打开看，也可以整包搬走。", "lead"), gap(4)]
    s += [table([
        ["文件", "装了什么", "丢了会怎样"],
        ["config.json", "Key、NapCat 地址、QQ 号、端口等配置", "需要重新填一次向导"],
        ["todos.json", "全部待办（含来源清单、时间依据）", "待办全没，但重新同步会从历史消息里补回来"],
        ["seen.json", "处理过的消息 ID + 你忽略过的消息", "可能重复提醒一遍旧消息"],
        ["ignore_keywords.json", "你教它忽略的关键词", "以前教的要重新教"],
        ["logs/app.log", "运行日志（超过 2MB 自动滚动）", "不影响功能，只影响排查"],
    ], [130, 210, 143])]

    s += [gap(6), H2("9.1　备份")]
    s += [P("把 <font name='YaHei-Bold'>todos.json</font> 和 <font name='YaHei-Bold'>config.json</font> 复制一份就是完整备份。"
           "程序自己也会在写入前留 <font name='YaHei-Bold'>todos.json.bak</font>，误改时可回退。")]

    s += [gap(4), H2("9.2　换电脑 / 多开一份")]
    s += [P("数据目录可以和代码分开放：设置环境变量 <font name='YaHei-Bold'>QQTODO_DATA_DIR</font>，"
           "config.json、todos.json、seen.json、logs 都会落在那个目录里。"
           "所以你可以把数据放在 U 盘或网盘目录，代码放在另一处；也能同时跑两份互不干扰的实例。")]

    # ---------------------------------------------------------------- 10
    s += [gap(10), H1("10　卸载"),
          P("在项目目录执行一句话即可：删除两个计划任务、结束后台进程，<b>数据文件全部保留</b>。"), ]
    s += [code_block(["powershell -ExecutionPolicy Bypass -File uninstall.ps1"])]
    s += [P("想彻底清干净，再手动删除项目目录（其中 config.json 含 Key，建议一并删掉）。", "small")]

    # ---------------------------------------------------------------- 11
    s += [PageBreak(), H1("11　常见问题")]
    faq = [
        ("网页打不开，或者打开是空白",
         "先看 logs/app.log 有没有“看板已就绪”。没有的话执行 Start-ScheduledTask -TaskName QQTodoBot 重新拉起；"
         "还不行就看端口是否被别的程序占用（config.json 里 board_port 改成 8090 再试）。"),
        ("状态一直显示“NapCat 未连接”",
         "核对 napcat_base_url 的端口和 napcat_access_token；确认 NapCat 窗口里还处在登录态。"
         "看板本身不受影响，历史待办照样能看。"),
        ("每次启动都还要扫码",
         "说明 napcat_qq_uin 没填或填错，或者这个号在本机没有成功登录过。NapCat 的快速登录要求该号本机登录过一次；"
         "换号或清了登录态就得再扫一次。"),
        ("第一次打开就跳到配置向导，看不到看板",
         "这是设计如此：没有可用 Key 时，看板让位给向导。填完 Key 保存即可进入；只想看看界面就点“直接进入看板”。"),
        ("填了 Key、测试也通过，但一条待办都不出现",
         "三个原因按顺序查：① 群消息本身没有“要做的事”（纯通知不算）；② napcat 没连上，本轮直接跳过；"
         "③ target_groups 填了群号但没包含你那个群。日志里“发现 N 条新消息”能直接定位。"),
        ("同一条通知还是出现了两张卡片",
         "两条消息的标题字面差异太大，或者里面的数字不同（附件2 和附件3 会被当成两件事，这是刻意的防误合并）。"
         "删掉多余那条即可，下一次同类转发会被合并。"),
        ("截止时间是空的，是不是没抓到？",
         "不是。原文里真的没写时间时，看板会显示“没写截止”，而不会拿消息发送时间冒充截止时间。这类事排在列表最后。"),
        ("AI 有时把不该算的消息也算成待办",
         "正常。用“这不是待办”教几次就会收敛；也可以把 deepseek_model 换成更强的模型。"),
        ("关机期间的群消息会丢吗？",
         "会。开机后能补拉 NapCat 历史记录范围内的消息（默认每群最近 50 条）。要 24 小时在线得让机器常开。"),
        ("会不会把我的群聊内容传到别处？",
         "只有“交给模型提炼”这一步会把消息文本发到 DeepSeek 接口，其余全部在本机完成；数据文件不会上传。"
         "介意的话可以只处理指定群（target_groups），或在不需要时直接关掉服务（第 10 章）。"),
    ]
    for i, (q, a) in enumerate(faq, 1):
        s += [Paragraph("<b>Q%d　%s</b>" % (i, q), S["body"]), gap(1),
              Paragraph("A　" + a, S["td"]), gap(7)]

    # ---------------------------------------------------------------- 附录
    s += [PageBreak(), H1("附录 A　配置项全表")]
    s += [table([
        ["字段", "默认值", "作用"],
        ["deepseek_api_key", "（空）", "模型 Key；也可用环境变量 DEEPSEEK_API_KEY 覆盖"],
        ["deepseek_base_url", "https://api.deepseek.com", "接口地址，换兼容 OpenAI 协议的模型时改这里"],
        ["deepseek_model", "deepseek-chat", "模型名，可换更强的版本"],
        ["napcat_base_url", "http://127.0.0.1:3000", "NapCat 的 OneBot HTTP 地址"],
        ["napcat_access_token", "（空）", "NapCat 的鉴权 token，没有就留空"],
        ["napcat_qq_uin", "（空）", "用于免扫码快速登录；填了才会自动拉起 NapCat"],
        ["napcat_exe", "（空）", "NapCatWinBootMain.exe 路径；留空则自动在常见目录里找"],
        ["target_groups", "[]", "只处理这些群号；空表示处理所有群"],
        ["history_count", "50", "每次每群拉多少条历史消息"],
        ["board_port", "8080", "看板端口，改完需要重启服务"],
        ["poll_interval_seconds", "180", "同步间隔（秒），最小 30"],
        ["auto_open_browser", "true", "启动后是否自动打开浏览器"],
        ["napcat_wait_seconds", "90", "等待 NapCat 就绪的最长时间"],
    ], [150, 150, 183])]

    s += [gap(10), H1("附录 B　一条待办的字段")]
    s += [table([
        ["字段", "含义"],
        ["title / detail", "一句话标题 / 完整说明"],
        ["published_at", "这条群消息发出的时间"],
        ["start_at", "任务开始时间；原文没写就是 null，绝不拿发布时间冒充"],
        ["deadline", "截止时间；解析不出来就是 null"],
        ["deadline_basis", "explicit 原文写明 / inferred 按原文推算 / none 没写"],
        ["deadline_raw", "原文里的那句话，例如“今晚9点前”，保证可追溯"],
        ["event_key", "同事件的指纹，用于合并"],
        ["sources[]", "来源清单：群名、发送者、消息 ID、时间、原文、confidence（exact 原始 / matched 转发匹配）"],
        ["done / created", "是否完成 / 入库时间"],
    ], [120, 363])]

    s += [gap(10), H1("附录 C　术语")]
    s += [table([
        ["词", "在这里指什么"],
        ["NapCat", "开源的 QQ 客户端框架，把群消息暴露成 HTTP 接口"],
        ["OneBot v11", "QQ 机器人类通用的消息协议，NapCat 按它提供服务"],
        ["提炼", "把一段群消息交给模型，问出“有没有需要我动手的事”"],
        ["合并", "把同一件事的多条消息合成一条待办，保留多来源"],
        ["来源待确认", "多条相似消息被系统判定为同一件事（matched），但标题并不完全一致"],
        ["看门狗", "每 2 分钟检查一次服务是否活着，挂了就拉起来"],
    ], [110, 373])]
    return s


# ================================================================ 产品说明书
def spec_story():
    s = []
    s += [H1("1　产品概述")]

    s += [H2("1.1　它是什么")]
    s += [P("QQ 待办助手是一个<b>运行在个人电脑上的本地优先工具</b>：接入你已登录的 QQ，按固定节奏扫描班级群、年级群、"
           "社团群的新消息，用大模型判断其中有没有“需要你动手”的要求，再把结果整理成一张可以直接划掉的待办看板。"
           "它由三部分组成——消息接入（NapCat）、AI 提炼（DeepSeek）与看板（本地网页），全部在一台机器上闭环运行。", "lead")]

    s += [gap(4), H2("1.2　要解决的真实问题")]
    s += [P("高校学生的信息分发高度集中在 QQ 群：通知、报名、交表、签到、领教材、竞赛报名、讲座信息混在一起，"
           "一天几十到上百条。这里有三个具体痛点：")]
    s += BUL([
        "<b>漏</b>：消息被刷走就再也找不回，重要的截止时间靠“记得”，而不是靠系统。",
        "<b>复</b>：同一份通知被班长、辅导员、任课老师分别转发，人在三个群里各看一遍，心里记三遍。",
        "<b>糊</b>：“今晚9点前”“本周五下班前”“月底前”这类模糊表述，需要自己换算成具体时间，还容易算错。",
    ])

    s += [gap(4), H2("1.3　产品做了什么选择")]
    s += [table([
        ["选择", "理由", "代价"],
        ["本地运行，不上云", "群聊内容涉及同学隐私；本地跑也省服务器成本", "需要一台常开的电脑"],
        ["模型只做语言理解，不做计算", "让大模型算日期、判重复容易错；代码做这些是确定的", "需要一套规则引擎，工程量更大"],
        ["保留原文与来源", "每条待办都能回溯到“哪条消息、谁说的、什么时候说的”", "数据结构更重"],
        ["把配置做成网页向导", "手改 JSON 是新手最大的门槛；测试按钮让错误当场暴露", "多一个页面要维护"],
        ["Windows 计划任务常驻", "学生用户不会为它开服务器", "关机期间抓不到消息"],
    ], [130, 200, 153])]

    s += [gap(6), callout("一句话概括产品定位：<b>一个装在电脑里的“班级群秘书”，把群里散落的要求收拢成一张不会漏的清单。</b>")]

    # ---------------------------------------------------------------- 2
    s += [PageBreak(), H1("2　目标用户")]

    s += [H2("2.1　核心用户画像")]
    s += [table([
        ["画像", "典型处境", "最痛的点", "对本产品的诉求"],
        ["高校在读学生（主）", "同时在上 5~10 个群：班级、年级、课程、社团、竞赛", "通知刷屏、截止日期靠记", "不漏事、不重复、能一眼看清今天要干嘛"],
        ["班级/社团干部（次）", "既要接收通知，又要向下转发并催进度", "重复劳动、统计谁交了", "把要求沉淀成清单，自己先不遗漏"],
        ["小团队协作成员", "项目群、实习群、兼职群信息混杂", "任务和闲聊混在一起", "只保留需要动手的部分"],
    ], [118, 165, 100, 100])]

    s += [gap(6), H2("2.2　使用门槛")]
    s += BUL([
        "会双击运行一个 .bat / 会复制粘贴一行命令即可；不需要写代码。",
        "首次配置全部在网页里完成，Key 与 NapCat 都能当场测试，错误有中文提示。",
        "需要理解并接受一个前提：<b>电脑要开着，QQ 要在线</b>。",
        "需要接受 NapCat 带来的账号风险（见《使用手册》3.2）。",
    ])

    s += [gap(6), H2("2.3　明确不服务的场景")]
    s += BUL([
        "不需要覆盖微信群、钉钉、飞书——本项目只做 QQ 群，把一条链路做深。",
        "不做多人协作与任务指派：没有账号体系，看板是本机的单人视图。",
        "不做消息回复与自动应答：只读不写，避免误发消息造成社交事故。",
        "不做云端 24 小时托管：那是另一种产品形态（需要服务器与合规成本）。",
    ])

    # ---------------------------------------------------------------- 3
    s += [PageBreak(), H1("3　核心功能")]

    s += [H2("3.1　功能矩阵")]
    s += [table([
        ["功能", "能力边界", "当前状态"],
        ["群消息采集", "按群拉取最近 N 条（默认 50）历史，跳过已处理的", "已实现"],
        ["AI 提炼", "输出结构化待办（标题、说明、原文时间说法）", "已实现"],
        ["时间解析", "中文相对时间 → 绝对时间，标注依据", "已实现，单测覆盖"],
        ["同事件合并", "跨群去重、数字冲突不合并、已完成不复活", "已实现，单测覆盖"],
        ["三视图看板", "列表 / 时间轴 / 日历，深浅色，手机自适应", "已实现"],
        ["纠错学习", "忽略关键词 + 忽略消息 ID 双记忆", "已实现"],
        ["常驻与自愈", "开机自启、看门狗、单实例、NapCat 重连", "已实现"],
        ["配置向导", "网页填 Key / NapCat，当场测试，立即生效", "已实现"],
        ["多端同步", "手机直接访问（需改监听地址）", "待开发"],
        ["多用户协作", "账号体系与共享清单", "规划中"],
    ], [110, 260, 113])]

    s += [gap(6), H2("3.2　看板")]
    s += [P("看板是整个产品唯一的高频界面，设计目标是“打开三秒就知道今天要做什么”。"
           "它不追求信息密度，而是把<b>紧迫度</b>变成位置：逾期的在最上面且用红色，今天的有剩余时间提示，"
           "没写截止的单独成组放在最后，不与有期限的事混在一起制造焦虑。")]
    s += [figure(os.path.join(SHOT, "board-list.png"), width=CONTENT_W,
                 caption="图 1　列表视图：按紧迫度分组，右侧给出剩余时间或“没写截止”", max_h=250)]

    s += [gap(8), H2("3.3　可追溯的来源清单")]
    s += [P("每条待办都带 sources 数组。同一份通知被三个群转发时，卡片上显示“另有 2 处来源”，展开可见每个群的名称、"
           "发送者、发送时间与原文引文，以及该来源是原文（exact）还是转发匹配（matched）。"
           "这是产品与“AI 随口总结”最重要的区别：<b>结论永远能回到证据</b>。")]

    # ---------------------------------------------------------------- 4
    s += [PageBreak(), H1("4　AI 的角色与价值")]

    s += [P("这一章说明“AI 到底干什么、为什么这样分工”，也是本项目在准确率与成本上的核心设计。", "lead"), gap(4)]

    s += [H2("4.1　职责边界")]
    s += [table([
        ["环节", "由谁做", "为什么"],
        ["判断“这段话里有没有要我做的事”", "AI", "语义判断，规则写不全：同一句“记得看群文件”在不同语境下含义不同"],
        ["抽取标题与说明", "AI", "概括与改写，人读起来才顺"],
        ["把“今晚9点前”照抄出来", "AI", "只做识别，不做换算，避免它算错日期"],
        ["把“今晚9点前”换算成 2026-10-26 21:00", "代码", "确定性算法，可单测，跨月跨周不会错"],
        ["判断两条消息是不是同一件事", "代码", "数字比对与字面重合度可解释；交给模型会时对时错且无法复现"],
        ["去重、幂等、已完成不复活", "代码", "状态管理必须是确定的"],
    ], [170, 60, 253])]

    s += [gap(6), callout("设计原则可以概括成一句：<b>让模型做它擅长的模糊判断，让代码做它擅长的精确计算。</b>"
                          "把日期换算交给模型，是同类产品最常见的错误来源。")]

    s += [gap(6), H2("4.2　时间是怎么说清楚的")]
    s += [P("模型只输出原文说法（deadline_raw），代码按消息发送时间做换算，并标注来源等级。以下是真实规则示例：")]
    s += [table([
        ["原文说法", "消息时间", "换算结果", "标注"],
        ["今晚9点前", "10-26 15:10", "10-26 21:00", "inferred（按原文推算）"],
        ["明天下午6点前", "10-26 15:10", "10-27 18:00", "inferred"],
        ["本周五下午6点前", "10-26 15:10", "10-30 18:00", "inferred"],
        ["下周五", "10-26", "11-06 23:59", "inferred"],
        ["10月9日12:00前", "10-06", "10-09 12:00", "explicit（原文写明）"],
        ["月底前", "10-26", "10-31 23:59", "inferred"],
        ["（没提时间）", "—", "null", "none（原文没写截止）"],
    ], [130, 100, 120, 133])]
    s += [gap(8)]
    s += [P("看板上“按原文推算”的小标签就是 inferred；“没写截止”意味着原文真的没有时间，而不是抓取失败——"
           "系统不会拿消息发送时间冒充截止时间。")]

    s += [gap(6), H2("4.3　同事件判定：怎么做到不重复")]
    s += NUM([
        "<b>标题归一</b>：先去掉“通知／请／提交／相关”这类通用词，再比字面重合度，避免“提交乙肝表”和“填写乙肝表”各存一条。",
        "<b>数字必须一致</b>：<font name='YaHei-Bold'>10月9日</font> 与 <font name='YaHei-Bold'>10月11日</font>、附件2 与附件3 一律视为两件事——宁可重复，不可误合并。",
        "<b>同批转发补挂来源</b>：同一轮抓到的相似消息不新开卡片，而是把来源补到已有条目的 sources 里，标为 matched。",
        "<b>已完成不复活</b>：已完成条目只要截止日相同，不会因为别的群转发又变成未完成。",
        "<b>换期限算新任务</b>：同名任务换了截止日期（比如下周的新表），正常作为新条目出现。",
    ])

    s += [gap(6), H2("4.4　AI 失败时怎么办")]
    s += BUL([
        "模型返回的不是合法 JSON：<b>丢弃本次结果</b>，把消息记为已处理并写日志，不污染待办数据，也不反复重试烧钱。",
        "Key 缺失或失效：看板顶部显示失败原因，并引导到配置向导；历史待办仍然可读。",
        "限流 429：记录错误、下一轮再试；已处理消息不会重复发送。",
        "NapCat 掉线：整轮跳过，不空转、不产生错误数据。",
    ])

    s += [gap(6), H2("4.5　成本")]
    s += [P("模型只在“本轮确实有新消息”时才被调用；没有新消息时零调用、零费用。"
           "按默认节奏（每 3 分钟一次）与中等活跃度（每天约 300 条新消息）估算：")]
    s += [table([
        ["项目", "估算口径", "数值"],
        ["输入 token", "每天约 1.5 万，月 45 万", "约 0.9 元/月"],
        ["输出 token", "每天约 2 千，月 6 万", "约 0.5 元/月"],
        ["合计", "按 deepseek-chat 官方价目估算", "约 1.4 元/月，一年约 17 元"],
    ], [110, 233, 140])]
    s += [gap(6)]
    s += [P("注：价格为按公开价目做的估算，实际以平台账单为准；本项目无服务器成本，其余开销只有你自己的电脑电费。", "small")]

    # ---------------------------------------------------------------- 5
    s += [PageBreak(), H1("5　技术实现思路")]

    s += [P("整套系统是“客户端—服务器—HTTP + JSON + 持久化”的一个完整小闭环，架构与运行流水线见下图：", "lead"), gap(2)]
    s += [figure(os.path.join(DIAG, "architecture.png"), width=330,
                 caption="图 2　整体架构（四个角色）与一次运行的流水线（八个步骤）", max_h=640)]

    s += [PageBreak(), H2("5.1　四个角色")]
    s += [table([
        ["角色", "职责", "技术选型"],
        ["QQ + NapCat", "持有登录态，把群消息暴露成 HTTP 接口", "NapCat，OneBot v11 协议"],
        ["main.py（中枢）", "既是客户端（向 NapCat、DeepSeek 要数据），也是服务器（给看板提供页面与接口）", "Python 标准库 + requests，无框架"],
        ["DeepSeek", "语义理解，返回结构化待办", "OpenAI 兼容的 chat/completions"],
        ["看板 index.html", "展示与操作", "单文件 HTML + 原生 JS，无构建、无依赖"],
    ], [110, 220, 153])]

    s += [gap(6), H2("5.2　一次运行的八个步骤")]
    s += [table([
        ["步骤", "做什么", "关键点"],
        ["1 拉消息", "get_group_list 拿群列表，get_group_msg_history 拉最近 N 条", "只处理配置允许的群"],
        ["2 转纯文本", "把分段消息（文本/图片/文件）拼成一句话", "图片记为 [图片]，文件记为 [文件 名字]"],
        ["3 去重", "按消息 ID 跳过已处理、按关键词跳过已教过的", "幂等：同一消息永不重复处理"],
        ["4 交 AI 提取", "只发新消息，要求返回 JSON", "无新消息则不调用"],
        ["5 合并清洗", "同事件判定、补挂来源、时间换算、字段规范化", "代码负责，可单测"],
        ["6 记录已处理", "把本批消息 ID 写入 seen.json", "下次不重复、不重复收费"],
        ["7 起看板", "http.server 提供页面与 /api 接口", "单实例、后台常驻"],
        ["8 人操作", "点完成/删除/忽略 → POST → 改 JSON", "操作即时落盘"],
    ], [78, 240, 165])]

    s += [gap(6), H2("5.3　数据结构")]
    s += [P("不用数据库，用 JSON 文件。理由：单用户、数据量小（一年几千条）、要能直接打开看、要能整包备份迁移。"
           "写入时先写临时文件再替换，并保留 .bak，避免断电写坏。")]
    s += [code_block([
        "{",
        '  "title": "填写并提交乙肝疫苗接种统计表（附件3）",',
        '  "published_at": "2026-10-26 15:10",',
        '  "start_at": null,',
        '  "deadline": "2026-10-26 21:00",',
        '  "deadline_basis": "inferred",        // explicit / inferred / none',
        '  "deadline_raw": "今晚9点前",          // 原文，可追溯',
        '  "event_key": "a1b2c3d4e5f6",        // 同事件指纹',
        '  "sources": [',
        '    {"group": "计科2班班群", "sender": "班长·小林", "msg_id": "101",',
        '     "time": "2026-10-26 15:10", "quote": "……", "confidence": "exact"},',
        '    {"group": "2026级计科年级群", "sender": "辅导员·周老师", "msg_id": "102",',
        '     "time": "2026-10-26 15:25", "quote": "……", "confidence": "matched"}',
        '  ],',
        '  "done": false',
        "}",
    ])]

    s += [gap(8), H2("5.4　部署与自愈")]
    s += [table([
        ["机制", "实现", "解决什么"],
        ["开机自启", "计划任务 QQTodoBot：登录桌面时启动 pythonw main.py --background", "不用每次手动开"],
        ["看门狗", "QQTodoBot-Watchdog 每 2 分钟探测端口，无响应则重拉主任务", "进程被强杀后自动恢复（实测约 40 秒）"],
        ["NapCat 守护", "连接失败按退避重试，必要时用 napcat_qq_uin 快速登录拉起 NapCat", "免扫码、掉线自愈"],
        ["单实例", "端口占用检测 + 进程互斥", "重复启动不会开出两个进程抢数据"],
        ["日志滚动", "logs/app.log 超过 2MB 滚动为 .1", "长期运行不撑爆磁盘"],
    ], [90, 268, 125])]

    s += [gap(6), H2("5.5　性能与规模")]
    s += BUL([
        "单轮处理量 = 群数 × 50 条上限，落在一次模型调用的合理窗口内；默认 3 分钟一轮，对 NapCat 与本机压力可以忽略。",
        "看板是静态 HTML + 一次 /api/todos 拉取，千级条目在浏览器里仍是毫秒级渲染。",
        "数据以 JSON 全量读写：一年几千条仍是百 KB 量级，暂无引入数据库的必要；若条目上万，可按月分文件或换 SQLite。",
    ])

    s += [gap(6), H2("5.6　隐私与安全")]
    s += BUL([
        "全部数据在本机；不做任何上传、不采集设备信息。",
        "只有“提炼”这一步把消息文本发给 DeepSeek；可用 target_groups 限定只处理必要的群。",
        "Key 只存在本地 config.json，并已加入 .gitignore；界面回显只露头尾，回显值不会覆盖真实 Key。",
        "看板只监听 127.0.0.1，同一局域网的其他设备访问不到（这也是手机暂时不能直接访问的原因）。",
        "仓库里的截图与演示数据全部为编造内容，不含真实群名与同学昵称。",
    ])

    s += [gap(6), H2("5.7　可扩展性")]
    s += BUL([
        "<b>换模型</b>：改 deepseek_base_url 与 deepseek_model 即可接任何 OpenAI 兼容接口。",
        "<b>换前端</b>：所有能力都在 /api 上，前端可以整体替换（已有 /api/todos、/api/todo/done|undo|delete|ignore、/api/sync、/api/config）。",
        "<b>换数据源</b>：NapCat 之后接任何 OneBot v11 实现都可以复用同一套采集逻辑。",
        "<b>加提醒</b>：截断点清楚——拿到 todo 后可以推送微信/邮件/桌面通知，不需要改动提炼层。",
    ])

    # ---------------------------------------------------------------- 6
    s += [PageBreak(), H1("6　应用场景示例")]

    s += [H2("6.1　场景一：一个班的日常（主线场景）")]
    s += [scenario([
        ("输入", "一天里班群 40 条、年级群 15 条、英语课群 8 条。其中三条是要求：今晚 9 点前交乙肝统计表、"
                 "今晚 11 点半前交实验报告纸质版、10 月 28 日 20:00 前报名市场调查大赛。"),
        ("系统的处理", "把“今晚9点前”换算成今天 21:00 并标注为推算；把年级群转发的那份统计表合并进同一条，"
                     "标为“另有 1 处来源”；把 40 条里的“收到”“谢谢老师”全部丢掉。"),
        ("输出与价值", "看板顶部三条，其中两条带剩余小时数，日历上 26 日与 28 日各有一个点；"
                     "从“翻群 + 记时间”变成“打开看一眼”，漏交的概率显著下降。"),
    ])]

    s += [gap(6), H2("6.2　场景二：社团与竞赛信息")]
    s += [scenario([
        ("输入", "竞赛群、培训群、学院通知里混着报名截止、扫码进群、培训时间。"),
        ("系统的处理", "报名类带明确截止时间，进“本周内”；“扫码加入培训群”这类没有截止时间的，"
                     "进“没写截止”分组，不会被当成紧急事项挤占视线，但也不会被丢掉。"),
        ("价值", "竞赛信息最容易“看到了但错过截止”。把截止日期变成日历上的一个点，是这类信息最需要的形态。"),
    ])]

    s += [gap(6), H2("6.3　场景三：课程群与作业")]
    s += [scenario([
        ("输入", "任课老师发“下周一上课时做词汇语法测试”“实验报告电子版发课程邮箱”。"),
        ("系统的处理", "区分“有明确期限”和“只说了要做”：有期限的进本周，没期限的进“没写截止”，"
                     "避免所有作业都堆在“今天”制造焦虑。"),
        ("价值", "把“模糊的长期要求”和“本周必须交的东西”分开放，人的注意力才能用在对的地方。"),
    ])]

    s += [gap(6), H2("6.4　场景四：小团队与实习兼职信息")]
    s += [scenario([
        ("输入", "项目群里的任务分派、兼职群里的报名方式、实习群里的投递截止。"),
        ("系统的处理", "用 target_groups 只处理这几个群，把生活群、家人群彻底排除在外，既不打扰也不越界。"),
        ("价值", "同一套工具，靠“选群”而不是“选功能”适配不同人群，这是它能从校园延伸到职场的原因。"),
    ])]

    # ---------------------------------------------------------------- 7
    s += [PageBreak(), H1("7　局限与演进路线")]
    s += [table([
        ["当前局限", "影响", "演进方向"],
        ["必须有一台开机的 Windows 电脑", "关机期间消息抓不到，只能补拉历史", "提供 Linux/Docker 部署，或轻量云托管"],
        ["只监听本机地址", "手机无法直接访问", "增加“允许局域网访问”开关与访问口令"],
        ["单个用户、无账号", "无法多人共享同一份清单", "账号体系 + 共享清单 + 指派"],
        ["只读 QQ 群", "不能回消息、不能催办", "按需增加“一键提醒自己”而不做自动回复，避免误发"],
        ["忽略规则基于关键词", "同义不同词仍可能重复提醒", "引入向量相似度做语义级忽略"],
        ["依赖 NapCat", "存在平台风控风险", "抽象数据源接口，支持官方机器人渠道"],
    ], [150, 173, 160])]

    # ---------------------------------------------------------------- 8
    s += [gap(10), H1("8　交付物与获取方式")]
    s += [table([
        ["内容", "位置"],
        ["源代码（Python + 单文件前端）", "仓库根目录 main.py / web/index.html"],
        ["一键安装脚本与看门狗", "install.ps1 / uninstall.ps1 / watchdog.ps1 / start.bat"],
        ["配置向导", "web/setup.html，运行时访问 /setup"],
        ["单元测试", "tests/test_core.py（时间换算、同事件判定、合并落库）"],
        ["演示数据与截图", "docs/demo-data / docs/screenshots（全部为编造内容）"],
        ["使用手册（本文档的姊妹篇）", "docs/手册与说明书/QQ待办助手-使用手册.pdf"],
    ], [200, 283])]
    s += [gap(6), P("运行环境：Windows 10/11 + Python 3.9 以上 + NapCat + 一个 DeepSeek Key。"
                    "除 DeepSeek 的 token 费用外无其他开销。")]
    return s


# ================================================================ 入口
def build_manual():
    cover_data = {
        "kicker": "AI 创新赛参赛作品 · 使用文档",
        "title": "QQ 待办助手",
        "tagline": "把群消息交给 AI，挑出真正需要你处理的事",
        "subtitle": "产品使用手册",
        "sub_lines": ["从安装到日常使用的完整说明，包含配置向导、看板操作与常见问题",
                      "适用版本 v1.0 · 2026 年 10 月"],
        "meta": [
            ("文档类型", "用户使用手册（面向使用者）"),
            ("配套文档", "《QQ 待办助手 · 产品说明书》"),
            ("运行环境", "Windows 10 / 11 + Python 3.9+ + NapCat + DeepSeek"),
            ("版本日期", "2026-10-26"),
        ],
        "shot": os.path.join(SHOT, "board-list.png"),
        "footer": "QQ 待办助手 · 产品使用手册 · v1.0",
    }
    story = cover_flow(cover_data) + toc_flow() + manual_story()
    path = os.path.join(OUT_DIR, "QQ待办助手-使用手册.pdf")
    return path, story, "QQ 待办助手 · 产品使用手册", "产品使用手册", cover_data


def build_spec():
    cover_data = {
        "kicker": "AI 创新赛参赛作品 · 产品文档",
        "title": "QQ 待办助手",
        "tagline": "群消息 → AI 提炼 → 待办看板，全部在你的电脑上完成",
        "subtitle": "产品说明书",
        "sub_lines": ["产品概述 · 目标用户 · 核心功能 · AI 的角色与价值 · 技术实现思路 · 应用场景",
                      "适用版本 v1.0 · 2026 年 10 月"],
        "meta": [
            ("文档类型", "产品说明书（面向评审与协作者）"),
            ("配套文档", "《QQ 待办助手 · 产品使用手册》"),
            ("技术栈", "Python 标准库 + requests / 原生前端 / NapCat / DeepSeek"),
            ("版本日期", "2026-10-26"),
        ],
        "shot": os.path.join(SHOT, "board-timeline.png"),
        "footer": "QQ 待办助手 · 产品说明书 · v1.0",
    }
    story = cover_flow(cover_data) + toc_flow(panel=digest()) + spec_story()
    path = os.path.join(OUT_DIR, "QQ待办助手-产品说明书.pdf")
    return path, story, "QQ 待办助手 · 产品说明书", "产品说明书", cover_data


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    built, blocked = [], []
    import time
    for builder in (build_manual, build_spec):
        path, story, title, footer, cover_data = builder()
        tmp = path + ".building"
        build(tmp, story, title, footer, cover_data)
        # 目标文件可能正被 PDF 阅读器打开，替换失败就重试一会儿
        for attempt in range(12):
            try:
                os.replace(tmp, path)
                built.append(path)
                break
            except PermissionError:
                time.sleep(5)
        else:
            blocked.append((path, tmp))
    for p in built:
        print("已生成 %s（%.1f KB）" % (p, os.path.getsize(p) / 1024))
    for path, tmp in blocked:
        print("未替换 %s：文件正被阅读器占用，新版本已存为 %s" % (path, tmp))


if __name__ == "__main__":
    main()
