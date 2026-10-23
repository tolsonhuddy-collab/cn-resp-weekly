"""1200x630 分享卡：大号 KPI + 流感季迷你图，配色与站点一致。"""
from PIL import Image, ImageDraw, ImageFont
import os
from . import metrics as M
FONTS = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
BG, INK, MUT, CUR, BLUE, BAND, GRID = "#fbfaf7", "#22262b", "#8a8d91", "#e4572e", "#1f4e6b", "#dcd8cf", "#ebe8e1"
LV = {"低于往年": (BLUE, "#e6eef3"), "高于往年": (CUR, "#fbe3d9"), "往年常见": ("#5d6166", "#ecebe7"), "—": (MUT, "#eeeeee")}
def _font(size, bold=False):
    p = FONTS[0] if bold else FONTS[1]
    return ImageFont.truetype(p, size, index=2) if os.path.exists(p) else ImageFont.load_default()

def _kpi(d, x, y, w, label, val, delta, p, focus=False):
    fg, bg = LV[M.level(p)]
    d.rounded_rectangle([x, y, x + w, y + 270], 18, fill="#fff8f5" if focus else "white", outline=CUR if focus else "#eeeae3", width=4 if focus else 2)
    if focus:
        d.rounded_rectangle([x + w - 130, y - 16, x + w - 16, y + 16], 16, fill=CUR); d.text((x + w - 120, y - 14), "重点关注", font=_font(22, True), fill="white")
    d.text((x + 22, y + 18), label, font=_font(24), fill="#5d6166")
    f = _font(96, True); txt = "—" if val is None else f"{val}"
    d.text((x + 22, y + 52), txt, font=f, fill=fg); tw = d.textlength(txt, font=f)
    d.text((x + 30 + tw, y + 118), "%", font=_font(28), fill=MUT)
    if delta is not None:
        a, ac = ("▲", CUR) if delta > 0.05 else (("▼", BLUE) if delta < -0.05 else ("■", MUT))
        d.text((x + 22, y + 184), "较上周", font=_font(22), fill=INK); d.text((x + 100, y + 182), f"{a} {abs(delta):.1f}", font=_font(24, True), fill=ac)
    L = M.level(p); lf = _font(20, True); lw = d.textlength(L, font=lf)
    d.rounded_rectangle([x + 22, y + 226, x + 42 + lw, y + 252], 13, fill=bg); d.text((x + 32, y + 226), L, font=lf, fill=fg)
    if p is not None: d.text((x + 52 + lw, y + 228), f"分位 {p}%", font=_font(20), fill=MUT)

def _mini(d, c, box):
    x0, y0, x1, y1 = box; NW = 31
    lo, hi = {}, {}
    for w in range(NW):
        vs = M.same_week(c.all, c.past, "pos_total", w)
        if vs: lo[w], _, hi[w] = M.quartiles(vs)
    cs = M.series(c.all, c.cur, "pos_total")
    m = max(list(hi.values()) + list(cs.values()) + [10]) * 1.1
    X = lambda w: x0 + w / (NW - 1) * (x1 - x0); Y = lambda v: y1 - v / m * (y1 - y0)
    ks = sorted(lo)
    if ks: d.polygon([(X(w), Y(hi[w])) for w in ks] + [(X(w), Y(lo[w])) for w in reversed(ks)], fill=BAND)
    d.line([(x0, y1), (x1, y1)], fill=GRID, width=2)
    pts = [(X(w), Y(cs[w])) for w in sorted(cs) if w < NW]
    if len(pts) > 1: d.line(pts, fill=CUR, width=7, joint="curve")
    if pts: px, py = pts[-1]; d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=CUR)
    for w, lab in [(0, "9月"), (9, "11月"), (17, "1月"), (26, "3月")]: d.text((X(w), y1 + 6), lab, font=_font(18), fill=MUT)
    d.text((x0, y0 - 30), "流感季对比 · 阳性率 %", font=_font(20, True), fill=INK)
    d.rectangle([x0, y1 + 36, x0 + 26, y1 + 42], fill=CUR); d.text((x0 + 32, y1 + 28), "今季", font=_font(18), fill=MUT)
    d.rectangle([x0 + 90, y1 + 32, x0 + 116, y1 + 46], fill=BAND); d.text((x0 + 122, y1 + 28), "往年 P25–P75", font=_font(18), fill=MUT)

def render(c, path):
    r = c.r; im = Image.new("RGB", (1200, 630), BG); d = ImageDraw.Draw(im)
    d.text((56, 40), "换季健康看板", font=_font(40, True), fill=INK)
    d.text((56, 96), f"{r['year']}年第{r['week']}周 · {r['week_start']}–{r['week_end']}", font=_font(24), fill=MUT)
    ks = [("流感阳性率（全国）", r.get("pos_total"), c.d("pos_total"), c.fp, c.focus == "流感病毒")]
    if c.mp:
        k2 = c.focus if c.focus and c.focus != "流感病毒" else "新型冠状病毒"
        from .site import NM
        v, dd, p = c.mpk(k2); ks.append((NM[k2] + "（门急诊）", v, dd, p, k2 == c.focus))
    else:
        ks.append(("南方 ILI%", r.get("ili_south"), c.d("ili_south"), M.pctl(r.get("ili_south"), c.sw("ili_south")), False))
    for i, k in enumerate(ks): _kpi(d, 56 + i * 330, 190, 300, *k)
    _mini(d, c, (740, 230, 1150, 440))
    d.line([(56, 545), (1144, 545)], fill=GRID, width=2); d.text((56, 565), "数据：中国国家流感中心、中国疾控中心 · 人群监测数据，不代表个人风险，不构成医疗建议", font=_font(20), fill=MUT)
    im.save(path, optimize=True)
