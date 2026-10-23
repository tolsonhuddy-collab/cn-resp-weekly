"""分位、分档、起始/峰值、重点关注规则。均为本站自定口径，非官方分级。"""
import statistics as st
EXCL = {"2019-20", "2020-21", "2021-22"}   # 2019-20 仅7周；2020-22 新冠防控期，流感活动异常
EXCL_NOTE = "2019-20（数据不全）、2020-21、2021-22（新冠防控期）不计入基线"

def pctl(v, arr):
    """arr 中严格低于 v 的比例（0–100）。"""
    if v is None or not arr: return None
    return round(100 * sum(a < v for a in arr) / len(arr))

def level(p):
    if p is None: return "—"
    return "低于往年" if p < 25 else ("高于往年" if p > 75 else "往年常见")

def series(recs, season, key):
    return {r["season_week"]: r[key] for r in recs if r.get("season") == season and r.get(key) is not None}

def baseline(recs, cur_season):
    return sorted({r["season"] for r in recs if r.get("season") and r["season"] < cur_season and r["season"] not in EXCL})

def same_week(recs, past, key, w, win=1):
    out = []
    for s in past:
        d = series(recs, s, key)
        out += [d[x] for x in range(w - win, w + win + 1) if x in d]
    return out

def quartiles(vals):
    vals = sorted(vals)
    if len(vals) == 1: return vals[0], vals[0], vals[0]
    q = st.quantiles(vals, n=4, method="inclusive")
    return q[0], q[1], q[2]

def onset_peak(d, thr=10.0, trough_within=12):
    """d: {season_week: 阳性率}。先找季初（前13周）低谷，低谷后首次由<thr升至≥thr为起始周；
    低谷后最高为峰值。季初一直≥thr 返回 '延续'。返回 (onset, peak_week, peak_value)。"""
    if not d: return None, None, None
    ks = sorted(d)
    early = [w for w in ks if w <= trough_within] or ks[:1]
    tr = min(early, key=lambda w: d[w])
    after = [w for w in ks if w >= tr]
    pk = max(after, key=lambda w: d[w])
    on = next((w for w in after if w > 0 and w <= pk and d[w] >= thr and d.get(w - 1, 1e9) < thr), None)
    if on is None and d[tr] >= thr: on = "延续"
    return on, pk, d[pk]

FOCUS_RULE = "规则：本周分位>P75且较上周上升者中涨幅最大；若无，取涨幅最大者（流感用往年同期分位）"
def focus(cands):
    """cands: [(name, value, wow_delta, pctl)] → name"""
    cands = [c for c in cands if c[2] is not None]
    if not cands: return None
    hot = [c for c in cands if (c[3] or 0) > 75 and c[2] > 0]
    return max(hot or cands, key=lambda c: c[2])[0]
