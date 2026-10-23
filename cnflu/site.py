import json
"""静态站点：家庭版（index）、专业版（pro）、按周 JSON、RSS。图表优先，文字只限标题/轴/图例/单位/来源。"""
import html, json, shutil, pathlib, statistics as st, datetime as dt
from email.utils import format_datetime
from . import metrics as M, card

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site"
SITE_URL = "https://tolsonhuddy-collab.github.io/cn-resp-weekly/"
C = dict(bg="#fbfaf7", ink="#22262b", mut="#8a8d91", grid="#ebe8e1", cur="#e4572e", blue="#1f4e6b", lb="#9cc0d6",
         band="#dcd8cf", lo="#e6eef3", hi="#fbe3d9")
LV = {"低于往年": (C["blue"], C["lo"]), "高于往年": (C["cur"], C["hi"]), "往年常见": ("#5d6166", "#ecebe7"), "—": (C["mut"], "#eee")}
NM = {"新型冠状病毒": "新冠", "流感病毒": "流感", "呼吸道合胞病毒": "合胞病毒", "腺病毒": "腺病毒", "人偏肺病毒": "人偏肺", "副流感病毒": "副流感",
      "普通冠状病毒": "普通冠状", "博卡病毒": "博卡", "鼻病毒": "鼻病毒", "肠道病毒": "肠道病毒", "肺炎支原体": "支原体"}
TIP = {"流感": "流感病毒：甲流（H1N1、H3N2型）和乙流", "合胞病毒": "呼吸道合胞病毒（RSV），婴幼儿常见", "人偏肺": "人偏肺病毒（hMPV）", "支原体": "肺炎支原体，不是病毒"}
DISC = "人群监测数据，不代表个人风险，不构成医疗建议"
esc = lambda x: html.escape(str(x))
slug = lambda r: f"{r['year']}-W{r['week']:02d}"

def arrow(d):
    if d is None: return "", C["mut"]
    return ("▲", C["cur"]) if d > 0.05 else (("▼", C["blue"]) if d < -0.05 else ("■", C["mut"]))

def spark(vals, w=90, h=24, col=None):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2: return ""
    m = max(vals) or 1; n = len(vals)
    pts = " ".join(f"{i*w/(n-1):.1f},{h-2-v/m*(h-4):.1f}" for i, v in enumerate(vals)); x, y = pts.split()[-1].split(",")
    return f'<svg width="{w+6}" height="{h}" aria-hidden="true"><polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.6"/><circle cx="{x}" cy="{y}" r="2.6" fill="{col}"/></svg>'

def pill(p):
    L = M.level(p); fg, bg = LV[L]
    return f'<span class="pill" style="color:{fg};background:{bg}">{L}</span>'

def kpi(label, val, d, p, ptip, focus=False, tip=None, unit="%"):
    a, ac = arrow(d); fg = LV[M.level(p)][0]
    lab = f'<span class="tip" title="{esc(tip)}">{label}</span>' if tip else label
    dd = "—" if d is None else f"{a} {abs(d):.1f}"
    return (f'<div class="k{" fx" if focus else ""}">{"<em>重点关注</em>" if focus else ""}<div class="kl">{lab}</div>'
            f'<div class="kv" style="color:{fg}">{"—" if val is None else val}<small>{unit}</small></div>'
            f'<div class="kd">较上周 <b style="color:{ac}" class="tip" title="单位：百分点">{dd}</b></div>'
            f'<div>{pill(p)} <span class="tip kp" title="{esc(ptip)}">分位 {"—" if p is None else str(p)+"%"}</span></div></div>')

def chips(items):
    return '<div class="cs">' + "".join(f'<span><i>{a}</i><b style="color:{c or C["ink"]}">{b}</b></span>' for a, b, c in items) + "</div>"

# ---------- 上下文 ----------
class Ctx:
    def __init__(self, flu, mp, i):
        self.all = [r for r in flu[: i + 1] if not r.get("missing")]
        self.r = flu[i]; self.prev = next((x for x in reversed(flu[:i]) if not x.get("missing")), None)
        self.cur = self.r["season"]; self.fw = self.r["season_week"]
        self.past = M.baseline(self.all, self.cur)
        self.seasons = sorted({x["season"] for x in self.all})
        self.flt = f"分位：往年同期（±1周；{'、'.join(self.past) or '无'}）中低于本周值的比例；{M.EXCL_NOTE}"
        sw = lambda k: M.same_week(self.all, self.past, k, self.fw)
        self.sw = sw
        self.fp = M.pctl(self.r.get("pos_total"), sw("pos_total"))
        mpi = [m for m in mp if m["week_end"] <= self.r["week_end"]]
        self.mp = mpi[-20:] if mpi and mpi[-1]["week_end"] == self.r["week_end"] else []
        self.mpall = mpi
        self.mptip = f"分位：{mpi[0]['week_end'][:7] if mpi else ''}以来该病原全部周次中低于本周值的比例"
        self.focus = None
        if self.mp:
            cands = []
            for k in NM:
                v, d, p = self.mpk(k)
                if k == "流感病毒": p = self.fp
                cands.append((k, v, d, p))
            self.focus = M.focus(cands)
    def d(self, k):
        a, b = self.r.get(k), (self.prev or {}).get(k)
        return None if a is None or b is None else round(a - b, 1)
    def mpk(self, k, f="ili"):
        if not self.mp or k not in self.mp[-1]["p"]: return None, None, None
        v = self.mp[-1]["p"][k].get(f); d = self.mp[-1]["p"][k].get(f + "_d")
        hist = [m["p"][k][f] for m in self.mpall if k in m["p"] and m["p"][k].get(f) is not None]
        return v, d, M.pctl(v, hist)
    def data(self):
        """供 BYOK 解读的页面数据（只含本页数字）。"""
        r = self.r
        o = {"周次": f"{r['year']}年第{r['week']}周", "日期": f"{r['week_start']}至{r['week_end']}",
             "流感阳性率_全国": r.get("pos_total"), "较上周": self.d("pos_total"), "往年同期分位": self.fp,
             "南方ILI%": r.get("ili_south"), "北方ILI%": r.get("ili_north"), "南方阳性率": r.get("pos_south"), "北方阳性率": r.get("pos_north"),
             "H3N2占甲流%": None if not r.get("a_total") else round(100 * (r.get("h3n2_total") or 0) / r["a_total"], 1)}
        if self.mp:
            o["各病原门急诊阳性率"] = {NM[k]: {"本周": v["ili"], "较上周": v.get("ili_d")} for k, v in self.mp[-1]["p"].items()}
            o["重点关注"] = NM.get(self.focus)
        return o

# ---------- 图 ----------
def season_chart(c, key="pos_total", W_=640, H=260, yl="流感阳性率 %", show_lvl=True, NW=31):
    lo, hi, med = {}, {}, {}
    for w in range(NW):
        vs = M.same_week(c.all, c.past, key, w)
        if vs: lo[w], med[w], hi[w] = M.quartiles(vs)
    cs = M.series(c.all, c.cur, key)
    allv = list(hi.values()) + list(cs.values()) or [10]
    m = max(allv) * 1.15 or 10; L, B = 34, 24
    X = lambda w: L + w / (NW - 1) * (W_ - L - 8); Y = lambda v: H - B - v / m * (H - B - 10)
    ks = sorted(lo); P = lambda d: " ".join(f"{X(w):.1f},{Y(d[w]):.1f}" for w in ks); PR = lambda d: " ".join(f"{X(w):.1f},{Y(d[w]):.1f}" for w in reversed(ks))
    g = f'<svg viewBox="0 0 {W_} {H}" class="ch" role="img" aria-label="流感季对比">'
    if show_lvl and ks:
        g += f'<polygon points="{X(ks[0])},{Y(m)} {X(ks[-1])},{Y(m)} {PR(hi)}" fill="{C["hi"]}"/><polygon points="{P(lo)} {X(ks[-1])},{Y(0)} {X(ks[0])},{Y(0)}" fill="{C["lo"]}"/>'
    step = 10 if m > 25 else 5
    for v in range(0, int(m) + 1, step):
        g += f'<line x1="{L}" x2="{W_-8}" y1="{Y(v)}" y2="{Y(v)}" stroke="{C["grid"]}"/><text x="{L-4}" y="{Y(v)+4}" class="ax" text-anchor="end">{v}</text>'
    for w, lab in [(0, "9月"), (9, "11月"), (17, "1月"), (26, "3月")]:
        g += f'<text x="{X(w)}" y="{H-6}" class="ax">{lab}</text>'
    if ks:
        g += f'<polygon points="{P(hi)} {PR(lo)}" fill="{C["band"]}" opacity=".6"/><polyline points="{P(med)}" fill="none" stroke="#a9a296" stroke-width="1.2" stroke-dasharray="4 3"/>'
    cw = sorted(w for w in cs if w < NW)
    if cw:
        pts = " ".join(f"{X(w):.1f},{Y(cs[w]):.1f}" for w in cw)
        g += (f'<polyline class="ln" pathLength="1" points="{pts}" fill="none" stroke="{C["cur"]}" stroke-width="3.6" stroke-linecap="round"/>'
              f'<polyline class="flow" pathLength="1" points="{pts}" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round"/>')
        lw = cw[-1]; a, col = arrow(cs[lw] - cs[cw[-2]] if len(cw) > 1 else None)
        g += f'<circle class="pt" cx="{X(lw)}" cy="{Y(cs[lw])}" r="5" fill="{C["cur"]}"/><text x="{X(lw)+9}" y="{Y(cs[lw])+5}" fill="{col}" font-size="15" font-weight="700">{a} {cs[lw]}</text>'
    g += f'<text x="{L}" y="12" class="ax">{yl}</text></svg>'
    lg = (f'<div class="lg"><i style="background:{C["cur"]}"></i>今季 {c.cur} <i style="background:{C["band"]};height:10px"></i>'
          f'<span class="tip" title="{esc(c.flt)}">往年 P25–P75</span> <i style="background:#a9a296;height:2px"></i>往年中位')
    if show_lvl: lg += f' <i style="background:{C["lo"]};height:10px"></i>低于往年 <i style="background:{C["hi"]};height:10px"></i>高于往年'
    return g + lg + "</div>"

def bars(c, f):
    last = c.mp[-1]["p"]; ks = [k for k in NM if k in last and last[k].get(f) is not None]
    rows = sorted(ks, key=lambda k: -last[k][f]); mx = max(last[k][f] for k in ks) or 1; out = ""
    for k in rows:
        v, d, p = c.mpk(k, f); a, col = arrow(d); n = NM[k]
        t = f' title="{TIP[n]}" class="tip"' if n in TIP else ""
        out += (f'<div class="br{" bfx" if k == c.focus else ""}"><span{t}>{n}</span><div class="bt"><div class="bf" style="width:{v/mx*100:.0f}%;'
                f'background:{C["cur"] if k == c.focus else "#b9b4aa"}"></div><b>{v}</b></div><i class="chip" style="color:{col}">{a}{"" if d is None else abs(d)}</i>'
                f'<span class="dot" style="background:{LV[M.level(p)][0]}" title="{M.level(p)} 分位{p}%"></span>{spark([x["p"].get(k, {}).get(f) for x in c.mp], 64, 20, col)}</div>')
    return out

def tiles(c):
    h = ""
    for k in ["流感病毒", "新型冠状病毒", "呼吸道合胞病毒", "肺炎支原体", "鼻病毒", "人偏肺病毒"]:
        v, d, p = c.mpk(k); a, col = arrow(d)
        h += (f'<div class="tl" style="border-top:3px solid {col}{";outline:2px solid " + C["cur"] if k == c.focus else ""}"><div class="tn">{NM[k]}</div>'
              f'<div class="ta" style="color:{col}">{a}</div><div class="tv">{v}<small>%</small></div>{spark([x["p"].get(k, {}).get("ili") for x in c.mp][-8:], 96, 30, col)}</div>')
    return h

def strip(c):
    r = c.r; h = '<div class="ks">'
    h += kpi("流感阳性率", r.get("pos_total"), c.d("pos_total"), c.fp, c.flt, focus=c.focus == "流感病毒", tip="全国流感阳性率：哨点医院流感样病例标本中流感阳性比例")
    h += kpi("南方 ILI%", r.get("ili_south"), c.d("ili_south"), M.pctl(r.get("ili_south"), c.sw("ili_south")), c.flt, tip="南方流感样病例占比 ILI%：门急诊就诊者中流感样病例的占比；周报未给出全国值")
    if c.mp:
        show = ["新型冠状病毒", "呼吸道合胞病毒", "肺炎支原体"]
        for k in show:
            v, d, p = c.mpk(k); h += kpi(NM[k] + "阳性率", v, d, p, c.mptip, focus=c.focus == k, tip=NM[k] + "阳性率（门急诊哨点，中国疾控中心多病原体监测）")
        if c.focus and c.focus not in show + ["流感病毒"]:
            v, d, p = c.mpk(c.focus); h += kpi(NM[c.focus] + "阳性率", v, d, p, c.mptip + "｜" + M.FOCUS_RULE, focus=True, tip=NM[c.focus] + "阳性率（门急诊哨点）")
    return h + "</div>"

def family_body(c):
    r = c.r; b = ""
    if c.mp:
        last = c.mp[-1]["p"]; top = max(last, key=lambda k: last[k]["ili"] or 0)
        up = sum((v.get("ili_d") or 0) > 0 for v in last.values()); dn = sum((v.get("ili_d") or 0) < 0 for v in last.values())
        b += (f'<div class="cd"><h2 class="hx">本周各病原阳性率<span class="tabs tg"><a href="#" class="on" data-f="ili">门急诊</a> <a href="#" data-f="sari">住院</a></span></h2>'
              + chips([("最高", f"{NM[top]} {last[top]['ili']}%", C["cur"]), ("上升", f"{up} 种", C["cur"]), ("下降", f"{dn} 种", C["blue"]),
                       ("重点关注", f'<span class="tip" title="{M.FOCUS_RULE}">{NM.get(c.focus, "—")}</span>', C["cur"])])
              + f'<div class="lg" style="margin-bottom:6px"><span class="tip" title="有呼吸道症状的就诊者中检出该病原体的比例">阳性率 %</span> · 较上周 · <span class="tip" title="{c.mptip}">分位</span> · 近{len(c.mp)}周</div>'
              f'<div class="b-ili">{bars(c, "ili")}</div><div class="b-sari" style="display:none">{bars(c, "sari")}</div></div>')
    med = st.median(c.sw("pos_total")) if c.sw("pos_total") else None
    b += (f'<div class="cd"><h2>流感季对比</h2>' + chips([("本周", f"{r.get('pos_total')}%", C["cur"]), ("往年同期中位", "—" if med is None else f"{med:.1f}%", None),
          ("同期分位", "—" if c.fp is None else f"{c.fp}%", LV[M.level(c.fp)][0]), ("对比季数", f"{len(c.past)} 季", None)]) + season_chart(c) + "</div>")
    if c.mp:
        last = c.mp[-1]["p"]
        b += (f'<div class="cd"><h2>主要病原趋势</h2>' + chips([("较上周上升", f"{sum((v.get('ili_d') or 0) > 0 for v in last.values())} 种", C["cur"]),
              ("较上周下降", f"{sum((v.get('ili_d') or 0) < 0 for v in last.values())} 种", C["blue"])])
              + f'<div class="tg3">{tiles(c)}</div><div class="lg" style="margin-top:6px"><span style="color:{C["cur"]}">▲上升</span> <span style="color:{C["blue"]}">▼下降</span> · 较上周 · 近8周</div></div>')
    return b

def heat(c):
    cell, L = 17, 70; rows = [(s, M.series(c.all, s, "pos_total")) for s in c.seasons]
    avg = {}
    for w in range(53):
        v = [M.series(c.all, s, "pos_total").get(w) for s in c.past]; v = [x for x in v if x is not None]
        if v: avg[w] = round(st.mean(v), 1)
    rows.append(("往年平均", avg))
    g = f'<svg viewBox="0 0 {L+53*cell+4} {len(rows)*16+22}" class="ch" role="img" aria-label="流行季热力日历">'
    for i, (s, d) in enumerate(rows):
        g += f'<text x="0" y="{i*16+12}" class="ax" {"font-weight=700 style=fill:" + C["cur"] if s == c.cur else ""}>{s}{"*" if s in M.EXCL else ""}</text>'
        for w in range(53):
            v = d.get(w); col = "#f1efe9" if v is None else f"rgba(228,87,46,{min(v/50,1)*.95+.05:.2f})"
            g += f'<rect x="{L+w*cell}" y="{i*16}" width="{cell-1}" height="14" rx="2" fill="{col}"><title>{s} 第{w}周 {"无数据" if v is None else str(v)+"%"}</title></rect>'
    for w, lab in [(0, "9月"), (13, "12月"), (22, "2月"), (30, "4月"), (43, "7月")]:
        g += f'<text x="{L+w*cell}" y="{len(rows)*16+14}" class="ax">{lab}</text>'
    return g + f'</svg><div class="lg">流感阳性率 0 <i style="width:80px;height:8px;background:linear-gradient(90deg,#fbe9e3,#e4572e)"></i> 50%+ · <span class="tip" title="{M.EXCL_NOTE}">* 不计入基线</span></div>'

def lines(series, H=200, W_=360, yl="", NW=53):
    vals = [v for d, *_ in series for v in d.values()] or [1]
    m = max(vals) * 1.05 or 1; L = 44
    X = lambda w: L + w / (NW - 1) * (W_ - L - 4); Y = lambda v: H - 18 - v / m * (H - 28)
    g = f'<svg viewBox="0 0 {W_} {H}" class="ch"><text x="{L}" y="10" class="ax">{yl}</text>'
    raw = m / 4; mag = 10 ** (len(str(int(raw))) - 1); step = max(round(raw / mag) * mag, 1); v = 0
    while v <= m:
        g += f'<line x1="{L}" x2="{W_}" y1="{Y(v)}" y2="{Y(v)}" stroke="#ebe8e1"/><text x="{L-3}" y="{Y(v)+4}" class="ax" text-anchor="end">{int(v):,}</text>'; v += step
    lg = ""
    for d, col, nm, wd in series:
        ks = sorted(w for w in d if w < NW)
        if ks:
            pts = " ".join(f"{X(w):.1f},{Y(d[w]):.1f}" for w in ks); cur = col == C["cur"]
            g += f'<polyline class="ln" pathLength="1" points="{pts}" fill="none" stroke="{col}" stroke-width="{wd}"/>'
            if cur: g += (f'<polyline class="flow" pathLength="1" points="{pts}" fill="none" stroke="#fff" stroke-width="{wd}" stroke-linecap="round"/>'
                          f'<circle class="pt" cx="{X(ks[-1]):.1f}" cy="{Y(d[ks[-1]]):.1f}" r="4" fill="{col}"/>')
        lg += f'<i style="background:{col}"></i>{nm} '
    return g + f'</svg><div class="lg">{lg}</div>'

def cum(c, s):
    d = M.series(c.all, s, "tested_total"); p = M.series(c.all, s, "pos_total"); a = 0; o = {}
    for w in sorted(p): a += p[w] * (d.get(w) or 0) / 100; o[w] = round(a)
    return o

def share(x):
    t = (x.get("h1n1_total") or 0) + (x.get("h3n2_total") or 0) + (x.get("b_total") or 0) or 1
    return [round(100 * (x.get(k) or 0) / t, 1) for k in ("h3n2_total", "h1n1_total", "b_total")]

def mix(c):
    rows = [x for x in c.all if x.get("a_total") is not None][-52:]
    n = len(rows); Wd, Hh = 520, 200; g = f'<svg viewBox="0 0 {Wd} {Hh+18}" class="ch">'
    for i, x in enumerate(rows):
        y = Hh
        for v, col in zip(share(x), (C["cur"], C["blue"], C["lb"])):
            hh = v / 100 * Hh; y -= hh; g += f'<rect x="{i*Wd/n:.1f}" y="{y:.1f}" width="{Wd/n+.5:.1f}" height="{hh:.1f}" fill="{col}"><title>{x["week_end"]}</title></rect>'
    g += f'<text x="0" y="{Hh+14}" class="ax">{rows[0]["week_end"]}</text><text x="{Wd}" y="{Hh+14}" class="ax" text-anchor="end">{rows[-1]["week_end"]}</text></svg>'
    return g + f'<div class="lg"><i style="background:{C["cur"]}"></i>甲流（H3N2型） <i style="background:{C["blue"]}"></i>甲流（H1N1型） <i style="background:{C["lb"]}"></i>乙流</div>'

def pharma_body(c, nfl, nmp):
    r = c.r; on, pk, pv = M.onset_peak(M.series(c.all, c.cur, "pos_total"))
    pks = [M.onset_peak(M.series(c.all, s, "pos_total")) for s in c.past]
    ons = [o for o, _, _ in pks if isinstance(o, int)]
    tbl = ('<table class="tb"><tr><td>流行季</td><td><span class="tip" title="季初（前13周）低谷后阳性率首次由&lt;10%升至≥10%的周；第0周=9月1日起第1周；“延续”=季初未跌破10%">起始周</span></td>'
           '<td><span class="tip" title="季初低谷之后阳性率最高的周">峰值周</span></td><td>峰值%</td></tr>')
    for s in c.seasons:
        o, p_, v = M.onset_peak(M.series(c.all, s, "pos_total"))
        cls = "cu" if s == c.cur else ("ex" if s in M.EXCL else "")
        tbl += f'<tr class="{cls}"><td>{s}{"*" if s in M.EXCL else ""}</td><td>{"–" if o is None else o}</td><td>{p_}{"（至今）" if s == c.cur else ""}</td><td>{v}</td></tr>'
    tbl += "</table>"
    med = st.median(c.sw("pos_total")) if c.sw("pos_total") else None
    sn = "".join(kpi(l, r.get(k), c.d(k), M.pctl(r.get(k), c.sw(k)), c.flt, tip=t) for l, k, t in
                 [("南方 ILI%", "ili_south", "门急诊就诊者中流感样病例占比"), ("北方 ILI%", "ili_north", "门急诊就诊者中流感样病例占比"),
                  ("南方 阳性率", "pos_south", None), ("北方 阳性率", "pos_north", None)])
    lp = c.past[-1] if c.past else None
    greys = ["#e2ddd3", "#cfc9bd", "#a9a296", "#7d7a72"]
    cumS = [(cum(c, s), greys[-len(c.past[-4:]) + i], s, 1.4) for i, s in enumerate(c.past[-4:])] + [(cum(c, c.cur), C["cur"], c.cur, 3)]
    sn_series = [(M.series(c.all, c.cur, "pos_south"), C["cur"], "南方 今季", 3), (M.series(c.all, c.cur, "pos_north"), C["blue"], "北方 今季", 3)]
    if lp: sn_series += [(M.series(c.all, lp, "pos_south"), "#efc0b0", "南方 上季", 1.4), (M.series(c.all, lp, "pos_north"), "#a9c1d1", "北方 上季", 1.4)]
    s_now = share(r); s_prev = share(c.prev or r); cc = cum(c, c.cur)
    return f'''<div class="cd"><h2>流行季热力日历</h2>{chips([("覆盖", f"{c.seasons[0]} – {c.cur} · {len(c.seasons)} 季", None), ("往年基线", f"{len(c.past)} 季", None), ("今季至今峰值", f"{pv}%", C["cur"]), ("往年峰值中位", f"{st.median([p for _,_,p in pks]):.1f}%" if pks else "—", None)])}{heat(c)}</div>
<div class="g2"><div class="cd"><h2>流感季强度对比</h2>{chips([("本周", f"{r['pos_total']}%", C["cur"]), ("同期中位", "—" if med is None else f"{med:.1f}%", None), ("同期分位", f"{c.fp}%", LV[M.level(c.fp)][0])])}{season_chart(c, W_=520, H=260)}</div>
<div class="cd"><h2>起始与峰值</h2>{chips([("今季起始", str(on), C["cur"]), ("今季峰值周", f"{pk}", C["cur"]), ("往年起始中位", f"第{st.median(ons):.0f}周" if ons else "—", None)])}{tbl}</div></div>
<div class="cd"><h2>南方 vs 北方</h2><div class="sn"><div>{lines(sn_series, W_=760, H=300, yl="流感阳性率 %")}</div><div class="ks">{sn}</div></div></div>
<div class="g2"><div class="cd"><h2>累计阳性数</h2>{chips([("今季累计", f"{max(cc.values()) if cc else 0:,}", C["cur"]), ("上季同期", f"{cum(c, lp).get(c.fw, 0):,}" if lp else "—", None)])}{lines(cumS, W_=520, H=260, yl="例（估算=检测数×阳性率）")}</div>
<div class="cd"><h2>毒株构成（近52周）</h2>{chips([("H3N2", f"{s_now[0]}%", C["cur"]), ("H1N1", f"{s_now[1]}%", C["blue"]), ("乙流", f"{s_now[2]}%", "#5f8fae"), ("H3N2 较上周", f"{s_now[0]-s_prev[0]:+.1f}", None)])}{mix(c)}</div></div>
<div class="cd"><h2>下载</h2><a href="data/weekly.csv" download>weekly.csv · 流感周报 {nfl} 周</a> · <a href="data/weekly.json" download>weekly.json</a> · <a href="data/mp.json" download>mp.json · 11种病原体 {nmp} 周</a></div>'''

CSS = f"""*{{box-sizing:border-box}}body{{margin:0;background:{C['bg']};color:{C['ink']};font-family:'Noto Sans CJK SC','PingFang SC','Microsoft YaHei',sans-serif}}
.w{{max-width:780px;margin:0 auto;padding:14px}}.wide .w{{max-width:1080px}}.top{{display:flex;justify-content:space-between;align-items:center;gap:8px}}h1{{font-size:19px;margin:4px 0}}h1 a{{color:inherit;text-decoration:none}}
.tabs a{{font-size:13px;padding:5px 10px;border-radius:14px;text-decoration:none;color:{C['ink']};border:1px solid {C['grid']};white-space:nowrap}}.tabs a.on{{background:{C['ink']};color:#fff}}
.cd{{background:#fff;border-radius:14px;padding:14px;margin:12px 0;box-shadow:0 1px 3px #0001}}h2{{font-size:16px;margin:0 0 8px}}.hx{{display:flex;justify-content:space-between}}
.ks{{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:8px;margin:10px 0}}.k{{background:#fff;border-radius:12px;padding:10px 12px;box-shadow:0 1px 3px #0001;position:relative;border:1px solid #fff}}
.k.fx{{border:2px solid {C['cur']};background:#fff8f5}}.k em{{position:absolute;top:-9px;right:10px;background:{C['cur']};color:#fff;font-style:normal;font-size:11px;padding:1px 8px;border-radius:9px}}
.kl{{font-size:12px;color:#5d6166;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.kv{{font-size:30px;font-weight:700;line-height:1.15}}.kv small{{font-size:13px;margin-left:3px;color:{C['mut']};font-weight:400}}.k>div:last-child{{white-space:nowrap}}.kd{{font-size:12px;margin:2px 0 4px}}
.pill{{font-size:11px;padding:1px 8px;border-radius:9px;font-weight:700}}.kp{{font-size:11px;color:{C['mut']}}}
.cs{{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 8px}}.cs span{{display:flex;flex-direction:column}}.cs i{{font-style:normal;font-size:11px;color:{C['mut']}}}.cs b{{font-size:17px}}
.br{{display:grid;grid-template-columns:62px 1fr 44px 10px 70px;align-items:center;gap:6px;font-size:13px;margin:4px 0;padding:1px 3px;border-radius:6px}}.bfx{{background:#fff3ee;font-weight:700}}.bt{{display:flex;align-items:center;gap:5px}}.bf{{height:14px;border-radius:3px}}.bt b{{font-size:12px}}.dot{{width:8px;height:8px;border-radius:4px}}
.chip{{font-style:normal;font-size:11px;font-weight:700}}.tip{{border-bottom:1px dotted {C['mut']};cursor:help}}
.ch{{width:100%;height:auto}}.ax{{font-size:11px;fill:{C['mut']}}}
.lg{{font-size:12px;color:{C['mut']};display:flex;align-items:center;gap:5px;flex-wrap:wrap}}.lg i{{display:inline-block;width:16px;height:4px;border-radius:2px}}
.ng{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}.nc{{border:1px solid {C['grid']};border-radius:8px;padding:8px;min-width:0}}.tg{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.tc{{min-width:0}}@media(max-width:760px){{.ng,.tg{{grid-template-columns:repeat(2,1fr)}}}}.tg3{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}.tl{{background:{C['bg']};border-radius:10px;padding:8px}}.tn{{font-size:13px}}.ta{{float:right;font-size:20px;margin-top:-20px}}.tv{{font-size:22px;font-weight:700}}.tv small{{font-size:12px}}
.flow{{display:none}}
.motion .ln{{stroke-dasharray:1;stroke-dashoffset:1;transition:stroke-dashoffset 1s ease-out}}.motion .in .ln{{stroke-dashoffset:0}}
.motion .in .flow{{display:inline;stroke-dasharray:.08 .92;opacity:.45;animation:fl 6s linear 1s infinite}}@keyframes fl{{to{{stroke-dashoffset:-1}}}}
.motion .in .pt{{transform-box:fill-box;transform-origin:center;animation:pu 2.4s ease-in-out 1s infinite}}@keyframes pu{{50%{{transform:scale(1.5);opacity:.6}}}}
@media(prefers-reduced-motion:reduce){{.motion .ln{{stroke-dasharray:none;transition:none}}.motion .flow{{display:none}}.motion .pt{{animation:none}}}}
.wsb{{margin:6px 0 0}}.wsb select{{font:inherit;font-size:13px;padding:4px 8px;border:1px solid #dcd8cf;border-radius:8px;background:#fff;color:{C["ink"]}}}.ft{{font-size:11px;color:{C['mut']};margin:14px 0}}.ft a{{color:{C['mut']}}}.g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.sn{{display:grid;grid-template-columns:2fr 1fr;gap:12px;align-items:start}}.sn .ks{{grid-template-columns:1fr 1fr;margin:0}}
.tb{{width:100%;font-size:12px;border-collapse:collapse}}.tb td{{padding:3px 2px;border-top:1px solid {C['grid']}}}.tb tr:first-child td{{color:{C['mut']};border:0}}.tb .cu{{color:{C['cur']};font-weight:700}}.tb .ex{{color:#b0b0b0}}
.nav{{display:flex;justify-content:space-between;font-size:13px}}.nav a{{color:{C['blue']}}}.arc a{{display:inline-block;margin:2px;padding:3px 6px;border-radius:6px;font-size:12px;text-decoration:none;color:{C['ink']}}}
@media(max-width:760px){{.g2,.sn{{grid-template-columns:1fr}}.ks{{grid-template-columns:1fr 1fr}}}}
.api textarea,.api input{{width:100%;padding:8px;border:1px solid {C['grid']};border-radius:8px;font:inherit}}.api button{{margin-top:6px;padding:7px 14px;border:0;border-radius:8px;background:{C['blue']};color:#fff}}.api #ao{{white-space:pre-wrap;font-size:14px;margin-top:8px}}"""

MOTION = True  # 网站动效开关（feed 与分享卡始终静态）
JS = """<script>
const MOTION=__MOTION__;  // 动效总开关：改 site.py 的 MOTION=False，或给 <html> 加 class="no-motion"
function init(){
const R=document.documentElement;if(MOTION&&!R.classList.contains('no-motion')&&!matchMedia('(prefers-reduced-motion: reduce)').matches){R.classList.add('motion');
const io='IntersectionObserver' in window?new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.25}):null;
document.querySelectorAll('svg').forEach(v=>{if(!v.querySelector('.ln,.pt'))return;io?io.observe(v):v.classList.add('in')})}
document.querySelectorAll('.tg').forEach(g=>g.querySelectorAll('a').forEach(a=>a.onclick=e=>{e.preventDefault();g.querySelectorAll('a').forEach(x=>x.classList.toggle('on',x==a));const cd=g.closest('.cd');['ili','sari'].forEach(f=>{const b=cd.querySelector('.b-'+f);if(b)b.style.display=f==a.dataset.f?'':'none'})}));
(function(){const k=document.getElementById('ak');if(!k)return;k.value=localStorage.getItem('deepseek_key')||'';
document.getElementById('ab').onclick=async()=>{const key=k.value.trim(),o=document.getElementById('ao');if(!key){o.textContent='请先填写 key';return}
localStorage.setItem('deepseek_key',key);o.textContent='生成中…';
const data=JSON.parse(document.getElementById('pd').textContent);
const sys='你是公共卫生数据解读助手。只依据用户提供的JSON数据，用简体中文写3-5句通俗解读：本周情况、与往年同期比较、涨落。不得编造数据、不预测、不给个人医疗建议、不推荐任何药品或品牌；涉及疫苗只说“请参考疾控部门建议”。结尾不需要免责声明。';
try{const r=await fetch('https://api.deepseek.com/chat/completions',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+key},
body:JSON.stringify({model:'deepseek-chat',temperature:0.2,messages:[{role:'system',content:sys},{role:'user',content:JSON.stringify(data)}]})});
const j=await r.json();o.textContent=r.ok?(j.choices[0].message.content+'\\n\\n（AI 生成，仅供参考；'+DISC+'）'):('请求失败：'+(j.error&&j.error.message||r.status))}catch(e){o.textContent='请求失败：'+e}};
document.getElementById('ax').onclick=()=>{localStorage.removeItem('deepseek_key');k.value=''}})();}
(function(){const sel=document.getElementById('ws'),box=document.getElementById('wk'),er=document.getElementById('we');
if(!sel){init();return}
const cache={},cur={v:sel.options[0].value};cache[cur.v]=box.innerHTML;
async function show(id){if(!id||id==cur.v||![...sel.options].some(o=>o.value==id)){sel.value=cur.v;return}
er.textContent='加载中…';box.style.opacity=.45;
try{if(!cache[id]){const r=await fetch('weeks/'+id+'.json');if(!r.ok)throw r.status;cache[id]=(await r.json()).html}
box.innerHTML=cache[id];cur.v=id;sel.value=id;er.textContent='';init()}
catch(e){sel.value=cur.v;er.textContent='该周数据加载失败，仍显示当前周'}box.style.opacity=''}
sel.onchange=()=>{history.replaceState(null,'','#w'+sel.value);show(sel.value)};
init();show(location.hash.replace(/^#w/,''));window.onhashchange=()=>show(location.hash.replace(/^#w/,''))})();
</script>""".replace("'+DISC+'", DISC).replace("__MOTION__", "true" if MOTION else "false")

def api_panel(c):
    return (f'<details class="cd api"><summary style="font-size:14px"><span class="tip" title="你的 key 只存在本机浏览器（localStorage），只会发送到 api.deepseek.com，不经过本站服务器">AI 文字解读（自备 DeepSeek API key）</span></summary>'
            f'<input id="ak" type="password" placeholder="sk-..." autocomplete="off"><button id="ab">生成</button> <button id="ax" style="background:#8a8d91">清除 key</button><div id="ao"></div></details>'
            f'<script type="application/json" id="pd">{json.dumps(c.data(), ensure_ascii=False).replace("</", "<\\/")}</script>')

def page(c, tab, body, depth=0, wide=False, extra="", weeks=None, tail=""):
    pre = "../" * depth; r = c.r
    src = f'数据：<a href="{esc(r.get("source_url") or r.get("pdf_url") or "")}">中国国家流感中心周报</a>'
    if c.mp: src += f'、<a href="{esc(c.mp[-1].get("url", "https://www.chinacdc.cn/jksj/jksj04_14275/"))}">中国疾控中心哨点监测</a>；多病原历史部分来自第三方整理 cn_cdc_crawl（已与自抓数据核对）'
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>换季健康看板 · {("家庭版", "专业版")[tab]} · {r["year"]}年第{r["week"]}周</title><meta name="description" content="换季健康看板{("家庭版", "专业版")[tab]}：中国流感与呼吸道病原体监测图表"><meta property="og:image" content="{pre}cards/{slug(r)}.png">'
            f'<link rel="alternate" type="application/rss+xml" href="{pre}feed.xml"><style>{CSS}</style></head><body class="{"wide" if wide else ""}"><div class="w">'
            f'<div class="top"><h1><a href="{pre}index.html">换季健康看板</a> {"" if weeks else f'<small style="font-size:12px;color:{C["mut"]}">{r["year"]}年第{r["week"]}周</small>'}</h1>'
            f'<div class="tabs"><a href="{pre}index.html" class="{"on" if tab == 0 else ""}">家庭版</a> <a href="{pre}pro.html" class="{"on" if tab == 1 else ""}">专业版</a></div></div>'
            + (f'<div class="wsb"><select id="ws" title="选择周次">' + "".join(f'<option value="{w}">{lab}</option>' for w, lab, _ in weeks) + '</select> <span id="we" class="lg"></span></div>'
               + f'<div id="wk">{strip(c)}{body}{api_panel(c)}</div>{tail}'  if weeks else f'{extra}{strip(c)}{body}{api_panel(c)}')
            + f'<div class="ft">{src} · 截至 {r["week_end"]}（{r["year"]}年第{r["week"]}周） · <a href="{pre}feed.xml">RSS</a> · {DISC}</div></div>{JS}</body></html>')

def new_months(nd, r):
    """本期周报发布日之前 7 天内新发布的月报 → feed 附一行"""
    if not nd: return []
    p = dt.date.fromisoformat(r.get("publish_date") or r["week_end"])
    return [m for m in nd["months"] if p - dt.timedelta(days=7) < dt.date.fromisoformat(m["pub"]) <= p]

def feed_item(c, url, nm=()):
    r = c.r; rows = [("流感阳性率（全国）", r.get("pos_total"), c.d("pos_total"), c.fp)]
    rows += [(NM[k] + "（门急诊）",) + c.mpk(k) for k in ["新型冠状病毒", "呼吸道合胞病毒", "肺炎支原体"]] if c.mp else []
    tr = "".join(f"<tr><td>{n}</td><td><b>{v}%</b></td><td>{arrow(d)[0]} {'' if d is None else abs(d)}</td><td>{M.level(p)}（分位{p}%）</td></tr>" for n, v, d, p in rows)
    body = (f'<p><img src="{SITE_URL}cards/{slug(r)}.png" alt="{r["year"]}年第{r["week"]}周"/></p>'
            f'<table><tr><th>指标</th><th>本周</th><th>较上周（百分点）</th><th>与往年比</th></tr>{tr}</table>'
            + (f'<p>重点关注：{NM.get(c.focus)}</p>' if c.focus else "")
            + "".join(f'<p>新月报：{m["ym"][:4]}年{int(m["ym"][5:])}月法定传染病 · ' + " · ".join(f'{SHORTN.get(k, k)} {v[0]:,}例' for k, v in m["d"].items() if k in ("流行性感冒", "百日咳", "猩红热", "流行性腮腺炎", "手足口病")) + '</p>' for m in nm)
            + f'<p>南方 ILI% {r.get("ili_south")}% · 北方 ILI% {r.get("ili_north")}% · 南方阳性率 {r.get("pos_south")}% · 北方阳性率 {r.get("pos_north")}%</p>'
            f'<p><small>{r["week_start"]}–{r["week_end"]} · 来源：中国国家流感中心、中国疾控中心 · {DISC}</small></p>')
    pub = dt.datetime.fromisoformat((r.get("publish_date") or r["week_end"]) + "T12:00:00+08:00")
    t = f'{r["year"]}年第{r["week"]}周 · 流感阳性率 {r.get("pos_total")}% · {M.level(c.fp)}'
    return (f"<item><title>{esc(t)}</title><link>{url}</link><guid isPermaLink='false'>cn-resp-weekly-{slug(r)}</guid><pubDate>{format_datetime(pub)}</pubDate>"
            f"<description><![CDATA[{body}]]></description></item>")

def build_site(flu, mpdata, nd=None, td=None):
    if OUT.exists(): shutil.rmtree(OUT)
    for d in ("cards", "data"): (OUT / d).mkdir(parents=True)
    mp = mpdata["records"]
    for f in ("weekly.csv", "weekly.json", "mp.json", "notif.json"):
        if (ROOT / "data" / f).exists(): shutil.copy(ROOT / "data" / f, OUT / "data" / f)
    real = [i for i, r in enumerate(flu) if not r.get("missing")]
    items = []
    # 单一仪表盘：每周只更新 index/pro；feed 每周一条（KPI 快照 + 分享卡），均链接到同一仪表盘
    for i in real[-30:]:
        c = Ctx(flu, mp, i); s = slug(c.r)
        card.render(c, OUT / "cards" / f"{s}.png")
        items.append(feed_item(c, f"{SITE_URL}#w{s}", new_months(nd, c.r)))
    wk = []
    for i in reversed(real[-30:]):
        cw = Ctx(flu, mp, i); r = cw.r
        wk.append((slug(r), f'{r["year"]}年第{r["week"]}周（{r["week_start"][5:]}–{r["week_end"][5:]}）', strip(cw) + family_body(cw) + api_panel(cw)))
    (OUT / "weeks").mkdir()
    for w, _, h in wk[1:]: (OUT / "weeks" / f"{w}.json").write_text(json.dumps({"week": w, "html": h}, ensure_ascii=False, separators=(",", ":")))
    c = Ctx(flu, mp, real[-1])
    (OUT / "index.html").write_text(page(c, 0, family_body(c), weeks=wk, tail=temp_section(td, c) + notif_section(nd)))
    (OUT / "pro.html").write_text(page(c, 1, pharma_body(c, len(real), len(mp)), wide=True))
    # 旧链接兼容：pharma.html → pro.html
    (OUT / "pharma.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=pro.html"><link rel="canonical" href="pro.html"><a href="pro.html">专业版</a>')
    now = format_datetime(dt.datetime.now(dt.timezone(dt.timedelta(hours=8))))
    (OUT / "feed.xml").write_text(f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>换季健康看板</title><link>{SITE_URL}</link>'
                                  f'<description>中国流感与呼吸道病原体监测周报（图表版）· {DISC}</description><language>zh-CN</language><lastBuildDate>{now}</lastBuildDate>'
                                  + "".join(reversed(items)) + "</channel></rss>")
    return len(real)

# ---------- 月报：常见传染病 ----------
RESP = ["流行性感冒", "百日咳", "猩红热", "流行性腮腺炎", "麻疹", "风疹", "肺结核", "人感染新亚型流感"]
ENTERIC = ["手足口病"]
SHORTN = {"流行性感冒": "流感", "流行性腮腺炎": "腮腺炎", "人感染新亚型流感": "新亚型流感"}
def fmtn(v):
    if v is None: return "—"
    return f"{v/10000:.1f}<small>万</small>" if v >= 100000 else f"{v:,}"

def _rng(lo, hi, cur, w=110):
    m = max(hi, cur) * 1.1 or 1; X = lambda v: 3 + v / m * (w - 6)
    return (f'<svg width="{w}" height="12" aria-hidden="true"><rect x="3" y="5" width="{w-6}" height="2" fill="{C["grid"]}"/>'
            f'<rect x="{X(lo):.1f}" y="2" width="{max(X(hi)-X(lo),2):.1f}" height="8" rx="2" fill="{C["band"]}"/>'
            f'<circle class="pt" cx="{X(cur):.1f}" cy="6" r="3.4" fill="{C["cur"]}"/></svg>')

def ncard(name, months, grp):
    ser = [m["d"].get(name, [None])[0] for m in months]; cur = ser[-1]; prev = ser[-2] if len(ser) > 1 else None
    y, mo = map(int, months[-1]["ym"].split("-"))
    past = [m["d"][name][0] for m in months[:-1] if m["ym"].endswith(f"-{mo:02d}") and name in m["d"]]
    pys = [m["ym"][:4] for m in months[:-1] if m["ym"].endswith(f"-{mo:02d}") and name in m["d"]]
    if cur is not None and prev:
        dv = cur - prev; a, col = ("▲", C["cur"]) if dv > 0 else (("▼", C["blue"]) if dv < 0 else ("■", C["mut"]))
        dd = f'<b style="color:{col}">{a} {abs(dv):,}</b> <span class="lg">{dv/prev*100:+.0f}%</span>'
    else: dd = "—"
    rg = (f'<div class="lg" style="margin-top:4px">{pys[0]}–{pys[-1]}年{mo}月 {min(past):,}–{max(past):,}</div>{_rng(min(past), max(past), cur)}'
          if past and cur is not None else "")
    sp = spark(ser[-24:], 120, 26, C["cur"] if grp == "r" else "#7a6a9e")
    return (f'<div class="nc"><div class="kl">{SHORTN.get(name, name)}</div><div class="kv" style="font-size:24px">{fmtn(cur)}<small>例</small></div>'
            f'<div class="kd">较上月 {dd}</div>{sp}{rg}</div>')

def notif_section(nd):
    if not nd or not nd.get("months"): return ""
    ms = nd["months"]; y, mo = map(int, ms[-1]["ym"].split("-"))
    tot = sum(ms[-1]["d"].get(n, [0])[0] for n in RESP)
    head = chips([("月报 · 截至", f"{y}年{mo}月", C["cur"]), ("呼吸道类合计", fmtn(tot) + "例", None),
                  ("覆盖", f'{ms[0]["ym"].replace("-", "年", 1)}月 – {y}年{mo}月 · {len(ms)} 月', None)])
    r = "".join(ncard(n, ms, "r") for n in RESP if n in ms[-1]["d"])
    e = "".join(ncard(n, ms, "e") for n in ENTERIC if n in ms[-1]["d"])
    return (f'<div class="cd" id="nd"><h2>常见传染病（月报）</h2>{head}<div class="lg" style="margin:4px 0">呼吸道传播</div><div class="ng">{r}</div>'
            + (f'<div class="lg" style="margin:10px 0 4px">肠道病毒（非呼吸道）</div><div class="ng">{e}</div>' if e else "")
            + f'<div class="lg" style="margin-top:8px">报告发病数（例）· 较上月 · 曲线近24月 · 灰带＝往年同月范围 · 来源：<a href="{esc(ms[-1]["url"])}">{esc(nd["source"])}</a></div></div>')

# ---------- 降温提醒（过去 7 天，非预报） ----------
def tchart(cy, thr, W_=200, H=96):
    d, hi, lo = cy["date"][1:], cy["tmax"][1:], cy["tmin"][1:]; n = len(d)
    vals = [v for v in hi + lo + cy["tmin"][:1] if v is not None]; a, b = min(vals) - 2, max(vals) + 2
    X = lambda i: 22 + i * (W_ - 30) / max(n - 1, 1); Y = lambda v: 6 + (b - v) / (b - a) * (H - 22)
    band = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(hi)) + " " + " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in reversed(list(enumerate(lo))))
    ln = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(lo))
    mk = "".join(f'<path d="M{X(i-1):.1f},{Y(lo[i-1])-12:.1f} l-5,-7 h10z" fill="{C["cur"]}"/>' for i in [j for j in cy["drops"]] if i - 1 < n)
    return (f'<svg viewBox="0 0 {W_} {H}" width="100%" role="img" aria-label="{cy["name"]}"><polygon points="{band}" fill="{C["lo"]}"/>'
            f'<polyline class="ln" pathLength="1" points="{ln}" fill="none" stroke="{C["blue"]}" stroke-width="2"/>'
            f'<polyline points="{" ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(hi))}" fill="none" stroke="{C["cur"]}" stroke-width="1.4"/>{mk}'
            f'<text x="0" y="{Y(b-2)+4:.0f}" font-size="9" fill="{C["mut"]}">{b-2:.0f}</text><text x="0" y="{Y(a+2)+4:.0f}" font-size="9" fill="{C["mut"]}">{a+2:.0f}</text>'
            f'<text x="{X(0):.0f}" y="{H-2}" font-size="9" fill="{C["mut"]}" text-anchor="middle">{d[0][5:]}</text><text x="{X(n-1):.0f}" y="{H-2}" font-size="9" fill="{C["mut"]}" text-anchor="end">{d[-1][5:]}</text></svg>')

def temp_section(td, c):
    if not td: return ""
    cs = td["cities"]; d0, d1 = cs[0]["date"][1], cs[0]["date"][-1]; r = c.r; thr = td["thr"]
    hit = [x["name"] for x in cs if x["drops"]]
    head = chips([("气温 · 过去7天", f"{d0[5:]} – {d1[5:]}", C["blue"]), ("流感周报", f'第{r["week"]}周 {r["week_start"][5:]} – {r["week_end"][5:]}', None),
                  (f"降温≥{thr:.0f}℃", f"{len(hit)} 城", C["cur"] if hit else None)])
    g = "".join(f'<div class="tc"><div class="kl">{x["name"]} <b style="color:{C["cur"] if x["drops"] else C["mut"]}">{len(x["drops"])}</b></div>{tchart(x, thr)}</div>' for x in cs)
    return (f'<div class="cd" id="tp"><h2>降温提醒</h2>{head}<div class="tg">{g}</div>'
            f'<div class="lg" style="margin-top:6px"><span style="color:{C["cur"]}">— 日最高</span> <span style="color:{C["blue"]}">— 日最低</span> ℃ · '
            f'<span style="color:{C["cur"]}">▼</span> 降温＝当日最低气温较前一日下降 ≥{thr:.0f}℃ · 实测/再分析，非预报 · 来源：<a href="https://open-meteo.com/">{td["source"]}</a></div></div>')
