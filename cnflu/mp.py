"""多病原体哨点监测（中国疾控中心 jksj04_14275 周报）。
自抓最近若干周 + 第三方历史 cn_cdc_crawl（github.com/dailypartita/cn_cdc_crawl），重叠周逐值交叉核对。"""
import re, csv, json, time, pathlib, datetime as dt, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "mp"
BASE = "https://www.chinacdc.cn/jksj/jksj04_14275/"
CRAWL_URL = "https://raw.githubusercontent.com/dailypartita/cn_cdc_crawl/main/data/cncdc_surveillance_all.csv"
CRAWL_SRC = "第三方整理：github.com/dailypartita/cn_cdc_crawl（与本站自抓重叠周已逐值核对）"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) cn-flu-weekly/0.1"}
PATHOGENS = ["新型冠状病毒","流感病毒","呼吸道合胞病毒","腺病毒","人偏肺病毒","副流感病毒","普通冠状病毒","博卡病毒","鼻病毒","肠道病毒","肺炎支原体"]

def _get(u):
    t = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
    time.sleep(1.5); return t

def parse_page(html):
    t = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html))
    m = re.search(r"(\d{4})年第(\d+)周（(\d{4})年(\d+)月(\d+)日", t)
    if not m: return None
    start = dt.date(int(m.group(3)), int(m.group(4)), int(m.group(5)))
    rec = {"year": int(m.group(1)), "week": int(m.group(2)), "week_end": (start + dt.timedelta(days=6)).isoformat(), "src": "cdc", "p": {}}
    for n in PATHOGENS:
        mm = re.search(n + r" ([\d.]+) ([+-]?[\d.]+) ([\d.]+) ([+-]?[\d.]+)", t)
        if mm: rec["p"][n] = {"ili": float(mm.group(1)), "ili_d": float(mm.group(2)), "sari": float(mm.group(3)), "sari_d": float(mm.group(4))}
    return rec if rec["p"] else None

def fetch_own(n_pages=2, offline=False):
    RAW.mkdir(parents=True, exist_ok=True)
    paths = []
    if not offline:
        for p in range(n_pages):
            try: paths += re.findall(r'href="\./(\d{6}/t\d+_\d+\.html)"', _get(BASE + ("index.html" if p == 0 else f"index_{p}.html")))
            except Exception as e: print("mp 列表失败", e)
    out = []
    for path in dict.fromkeys(paths):
        f = RAW / path.replace("/", "_")
        if not f.exists():
            try: f.write_text(_get(BASE + path))
            except Exception as e: print("mp 详情失败", path, e); continue
    for f in sorted(RAW.glob("*_t*.html")):
        r = parse_page(f.read_text())
        if r: r["url"] = BASE + f.name.replace("_", "/", 1); out.append(r)
    return out

def load_crawl(offline=False):
    f = RAW / "cn_cdc_crawl.csv"
    if not f.exists() and not offline:
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(CRAWL_URL, headers=UA), timeout=60).read())
    by = {}
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8")):
            e = by.setdefault(r["target_end_date"], {"year": int(r["target_end_date"][:4]), "week": int(r["report_week"]),
                                                    "week_end": r["target_end_date"], "src": "crawl", "p": {}})
            e["p"][r["pathogen"]] = {"ili": float(r["ili_percent"]) if r["ili_percent"] else None,
                                     "sari": float(r["sari_percent"]) if r["sari_percent"] else None}
    return by

def merge(own, crawl):
    """自抓优先；重叠周核对差异。返回 (records, check)。"""
    by = dict(crawl); n = bad = 0
    for r in own:
        c = crawl.get(r["week_end"])
        if c:
            for k, v in r["p"].items():
                if k in c["p"] and c["p"][k]["ili"] is not None:
                    n += 1; bad += abs(c["p"][k]["ili"] - v["ili"]) > 0.01
        by[r["week_end"]] = r
    recs = sorted(by.values(), key=lambda x: x["week_end"])
    for a, b in zip(recs, recs[1:]):   # 补算周环比（官方给出的优先）
        for k, v in b["p"].items():
            pv = a["p"].get(k, {})
            for f in ("ili", "sari"):
                if v.get(f + "_d") is None and v.get(f) is not None and pv.get(f) is not None:
                    v[f + "_d"] = round(v[f] - pv[f], 1)
    return recs, {"overlap_values": n, "mismatch": bad}

def build(offline=False):
    recs, chk = merge(fetch_own(offline=offline), load_crawl(offline=offline))
    return {"records": recs, "check": chk, "sources": {"cdc": "中国疾控中心 全国急性呼吸道传染病哨点监测情况", "crawl": CRAWL_SRC}}
