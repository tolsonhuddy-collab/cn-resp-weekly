"""把 CNIC 英文周报 PDF 文本解析为结构化记录。纯规则，无 LLM。"""
import re, subprocess, datetime as dt

MONTHS = {m: i for i, m in enumerate(["january","february","march","april","may","june","july",
          "august","september","october","november","december"], 1)}

def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout

def _norm(t):
    t = t.replace("（", "(").replace("）", ")").replace("％", "%").replace("，", ",")
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r"(\d)(?:st|nd|rd|th)(?=\b|\d)", r"\1 ", t)   # 旧版周报：May 17th–May 23th
    return re.sub(r"\s+", " ", t)

def _f(x):
    return None if x is None else float(x)

def _mon(x): return MONTHS3[x[:3].lower()]
MONTHS3 = {m[:3]: i for m, i in MONTHS.items()}

def _mk(m1, d1, y1, m2, d2, y2):
    m2 = m2 or m1; y2 = int(y2); mo1, mo2 = _mon(m1), _mon(m2)
    y1 = int(y1) if y1 else (y2 - 1 if mo1 > mo2 else y2)
    return dt.date(y1, mo1, int(d1)), dt.date(y2, mo2, int(d2))

def parse_dates(t):
    mon = r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)"
    pats = [(mon + r"\.?\s*(\d{1,2}),?\s*(\d{4})?\s*(?:to|-|–|~)\s*" + mon + r"?\.?\s*(\d{1,2}),?\s*(\d{4})\s*\(\s*Week\s*(\d+)", "new"),
            # 旧版（约2020–2022）："During week 20 (May 17th–May 23th 2021)"、"(Jul 26th–Aug 1st2021)"
            (r"week\s*(\d+)\s*\(\s*" + mon + r"\.?\s*(\d{1,2}),?\s*(\d{4})?\s*(?:to|-|–|~)\s*" + mon + r"?\.?\s*(\d{1,2}),?\s*(\d{4})\s*\)", "old")]
    fb = None
    for pat, kind in pats:
        for m in re.finditer(pat, t, re.I):
            g = m.groups()
            if kind == "new": m1, d1, y1, m2, d2, y2, wk = g
            else: wk, m1, d1, y1, m2, d2, y2 = g
            try: a, b = _mk(m1, d1, y1, m2, d2, y2)
            except (ValueError, KeyError): continue
            if (b - a).days == 6:      # 原文偶有月份笔误，取首个自洽的日期
                return a.isoformat(), b.isoformat(), int(wk)
            fb = fb or (b, int(wk))
    if fb:  # 原文起始日笔误（如 "June15 to 22"、"Oct 30 to Nov 12"）：以结束日为准，周一=结束日-6
        return (fb[0] - dt.timedelta(6)).isoformat(), fb[0].isoformat(), fb[1]
    return None, None, None

def parse_ili(t, region):
    # "... in southern provinces was 4.5%, lower than last week (4.6%)"
    m = re.search(region + r" provinces was\s*([\d.]+)%", t, re.I)
    if not m: return None, None
    seg = t[m.end(): m.end() + 260]
    lw = re.search(r"last week\s*\(([\d.]+)%\)", seg)
    return _f(m.group(1)), _f(lw.group(1)) if lw else None

def parse_same_period(t, region):
    """返回 {年份: ILI%}，来自'同期'比较句。"""
    m = re.search(region + r" provinces was\s*[\d.]+%(.{0,320}?)\(Figure", t, re.I)
    out = {}
    if not m: return out
    seg = m.group(1)
    for years, vals in re.findall(r"same week of\s*((?:\d{4}(?:\s*(?:,|and)\s*)?)+)\s*\(([\d.%\s,and]+)\)", seg):
        ys = re.findall(r"\d{4}", years); vs = re.findall(r"[\d.]+(?=%)", vals)
        for y, v in zip(ys, vs): out[int(y)] = float(v)
    return out

CELL = r"\s+(\d+)(?:\s*\(([\d.]+)%?\))?"
ROW = CELL * 3
def parse_table(t):
    r = {}
    m = re.search(r"specimens tested\s+(\d+)\s+(\d+)\s+(\d+)", t)
    if m: r["tested_south"], r["tested_north"], r["tested_total"] = map(int, m.groups())
    for key, label in [("pos", r"positive specimens\s*\(%\)"), ("a", r"Influenza A"),
                       ("h1n1", r"A\(H1N1\)pdm09"), ("h3n2", r"A\(H3N2\)"),
                       ("b", r"Influenza B"), ("vic", r"Victoria")]:
        m = re.search(label + ROW, t)
        if m:
            g = m.groups()
            # 计数为 0 时官方不写百分比，记为 0.0
            vals = [(_f(g[i+1]) if g[i+1] is not None else (0.0 if g[i] == "0" else None)) for i in (0, 2, 4)]
            r[f"{key}_south"], r[f"{key}_north"], r[f"{key}_total"] = vals
    return r

def parse_outbreaks(t):
    m = re.search(r"There (?:were|was)\s*(\d+|no)\s*ILI outbreaks?", t, re.I)
    if not m: return None
    return 0 if m.group(1).lower() == "no" else int(m.group(1))

def parse_vaccine_match(t):
    out = {}
    m = re.search(r"\d+\s*\(([\d.]+)%\)\s*influenza\s*A\(H1N1\)pdm09 viruses were characterized as\s*(\S+?)-like", t)
    if m: out["h1n1"] = (float(m.group(1)), m.group(2))
    m = re.search(r"\d+\s*\(([\d.]+)%\)\s*influenza\s*A\(H3N2\)\s*viruses\s*were\s*characterized\s*as\s*(\S+?\(cell\))-like", t)
    if not m:
        m = re.search(r"\d+\s*\(([\d.]+)%\)\s*influenza\s*A\(H3N2\)\s*viruses\s*were\s*characterized\s*as\s*(\S+?)-like", t)
    if m: out["h3n2"] = (float(m.group(1)), m.group(2))
    m = re.search(r"\d+\s*\(([\d.]+)%\)\s*influenza\s*B/Victoria\s*viruses\s*were\s*characterized\s*as\s*(\S+?)-like", t)
    if m: out["vic"] = (float(m.group(1)), m.group(2))
    return out

def parse_text(raw):
    t = _norm(raw)
    start, end, wk = parse_dates(t)
    rec = {"week_start": start, "week_end": end, "week": wk}
    rec["ili_south"], rec["ili_south_prev"] = parse_ili(t, "southern")
    rec["ili_north"], rec["ili_north_prev"] = parse_ili(t, "northern")
    rec["same_period_south"] = parse_same_period(t, "southern")
    rec["same_period_north"] = parse_same_period(t, "northern")
    rec.update(parse_table(t))
    rec["outbreaks"] = parse_outbreaks(t)
    vm = parse_vaccine_match(t)
    for k, (pct, strain) in vm.items():
        rec[f"match_{k}_pct"], rec[f"match_{k}_strain"] = pct, strain
    return rec
