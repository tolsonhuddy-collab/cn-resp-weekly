"""从缓存的原始 PDF 生成 data/、site/（静态页 + SVG 图 + feed.xml + 分享卡）。"""
import json, csv, os, html, datetime as dt, pathlib, sys
from email.utils import format_datetime
from . import parse, notif, temp

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW, DATA, SITE = ROOT / "raw", ROOT / "data", ROOT / "site"
DISCLAIMER = "人群监测数据，不代表个人风险，不构成医疗建议"
FIELDS = ["season", "season_week", "year", "week", "week_start", "week_end", "publish_date", "missing", "note",
          "ili_south", "ili_north", "pos_south", "pos_north", "pos_total", "a_total", "b_total",
          "h1n1_total", "h3n2_total", "vic_total", "h1n1_south", "h3n2_south", "h1n1_north", "h3n2_north",
          "outbreaks", "tested_total", "match_h1n1_pct", "match_h3n2_pct", "match_h3n2_strain", "match_vic_pct",
          "ili_south_prev", "ili_north_prev", "source_url", "pdf_url"]

def season_of(week_end):
    d = dt.date.fromisoformat(week_end)
    y = d.year if d >= dt.date(d.year, 9, 1) else d.year - 1   # 流感季：9月起算
    idx = (d - dt.date(y, 9, 1)).days // 7
    return f"{y}-{str(y+1)[2:]}", idx

def load_records():
    idx = json.loads((RAW / "index.json").read_text())
    recs, failed = [], set()
    for r in idx:
        pdf = RAW / "en" / f"{r['year']}-W{r['week']:02d}.pdf"
        meta = RAW / "en" / f"{r['year']}-W{r['week']:02d}.json"
        cache = RAW / "en" / f"{r['year']}-W{r['week']:02d}.parsed.json"   # 小缓存入库；PDF 不入库
        if pdf.exists():
            rec = parse.parse_text(parse.pdf_text(pdf))
            cache.write_text(json.dumps(rec, ensure_ascii=False))
        elif cache.exists():
            rec = json.loads(cache.read_text())
        else: continue
        rec.update(json.loads(meta.read_text()) if meta.exists() else {})
        rec["publish_date"] = rec.pop("page_date", None)
        rec["year"] = r["year"]; rec["source_url"] = r["detail_url"]; rec["missing"] = False; rec["note"] = ""
        if rec["week"] != r["week"]: rec["note"] = f"列表周次{r['week']}与PDF周次{rec['week']}不一致"
        if not rec["week_end"] or rec.get("pos_south") is None:
            print("WARN 解析失败", pdf); failed.add((r["year"], r["week"])); continue
        rec["season"], rec["season_week"] = season_of(rec["week_end"])
        recs.append(rec)
    recs.sort(key=lambda x: x["week_end"])
    # 显式标出缺失周
    out, d = [], dt.date.fromisoformat(recs[0]["week_end"])
    have = {r["week_end"]: r for r in recs}
    last = dt.date.fromisoformat(recs[-1]["week_end"])
    while d <= last:
        k = d.isoformat()
        if k in have: out.append(have[k])
        else:
            iso = d.isocalendar()
            s, i = season_of(k)
            note = "缺失：该周PDF为扫描图片，暂未OCR" if (iso[0], iso[1]) in failed else "缺失：官网列表中无该周周报"
            out.append({"season": s, "season_week": i, "year": iso[0], "week": iso[1], "week_end": k,
                        "week_start": (d - dt.timedelta(days=6)).isoformat(), "missing": True, "note": note})
        d += dt.timedelta(days=7)
    return out

def write_data(recs):
    DATA.mkdir(exist_ok=True)
    (DATA / "weekly.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1))
    with open(DATA / "weekly.csv", "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, extrasaction="ignore"); w.writeheader()
        for r in recs: w.writerow(r)

from .site import build_site
from . import mp as mpmod

def scrape_new():
    """联网时抓新周报；失败不影响构建（沿用缓存，不清空数据）。"""
    from . import scrape
    try:
        reps = scrape.list_reports(max_pages=3)
        if not reps: print("WARN CNIC 列表为空，沿用缓存"); return
        old = json.loads((RAW / "index.json").read_text()) if (RAW / "index.json").exists() else []
        have = {(r["year"], r["week"]) for r in old}
        new = [r for r in reps if (r["year"], r["week"]) not in have]
        for r in new:
            try:
                if scrape.fetch_pdf(r): old.append(r)
            except Exception as e: print("WARN 跳过", r["year"], r["week"], e)
        old.sort(key=lambda r: (r["year"], r["week"]), reverse=True)
        (RAW / "index.json").write_text(json.dumps(old, ensure_ascii=False, indent=1))
        print("CNIC 新周报", len(new))
    except Exception as e: print("WARN CNIC 抓取失败，沿用缓存", e)

def main():
    if "--offline" not in sys.argv: scrape_new()
    recs = load_records(); write_data(recs)
    mpd = mpmod.build(offline="--offline" in sys.argv)
    (DATA / "mp.json").write_text(json.dumps(mpd, ensure_ascii=False, indent=0))
    print("多病原体", len(mpd["records"]), "周；与第三方重叠核对", mpd["check"])
    if mpd["check"]["mismatch"]: print("WARN 第三方历史与自抓数据不一致", mpd["check"])
    off = "--offline" in sys.argv
    nd = notif.build(offline=off); (ROOT / "data" / "notif.json").write_text(json.dumps(nd, ensure_ascii=False))
    print("月报", len(nd["months"]), nd["months"][0]["ym"] if nd["months"] else "", "→", nd["months"][-1]["ym"] if nd["months"] else "")
    td = temp.build(offline=off)
    build_site(recs, mpd, nd, td)
    n = sum(not r["missing"] for r in recs)
    print(f"records={n} missing={len(recs)-n} range={recs[0]['week_end']}..{recs[-1]['week_end']}")

if __name__ == "__main__":
    main()
