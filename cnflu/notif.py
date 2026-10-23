"""中国疾控「全国法定传染病疫情概况」月报：抓取列表 + 解析呼吸道相关病种发病/死亡数。"""
import re, json, time, urllib.request, pathlib, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "notif"
BASE = "https://www.chinacdc.cn/jksj/jksj01/"
# 呼吸道传播为主的法定传染病 + 手足口病（肠道病毒，非呼吸道，单独标注）
DISEASES = ["流行性感冒", "百日咳", "猩红热", "流行性腮腺炎", "麻疹", "风疹", "肺结核", "人感染新亚型流感", "手足口病"]
SHORT = {"流行性感冒": "流感", "流行性腮腺炎": "腮腺炎", "人感染新亚型流感": "新亚型流感"}

def _get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (cn-resp-weekly research)"})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read().decode("utf-8", "replace")

def parse_list(html):
    """→ [(year, month, url, pub_date)]"""
    out = []
    for m in re.finditer(r'href="\./(\d{6})/t(\d{8})_(\d+)\.html"[^>]*>\s*(\d{4})年(\d{1,2})月全国(?:法定)?传染病疫情', html):
        d, p, i, y, mo = m.groups()
        out.append((int(y), int(mo), f"{BASE}{d}/t{p}_{i}.html", f"{p[:4]}-{p[4:6]}-{p[6:]}"))
    return out

def parse_page(html):
    """正文表格：病名 发病数 死亡数 → {病名: [发病, 死亡]}"""
    html = re.sub(r"<sup[^>]*>.*?</sup>", "", html, flags=re.S)  # 脚注序号
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace(",", "")
    out = {}
    for n in DISEASES:
        m = re.search(r"(?<![\u4e00-\u9fff])" + n + r" (\d+) (\d+)", t)
        if m: out[n] = [int(m.group(1)), int(m.group(2))]
    return out

def build(offline=False):
    RAW.mkdir(parents=True, exist_ok=True)
    idx = RAW / "index.json"
    items = []
    if not offline:
        try:
            for n in range(0, 20):
                try: h = _get(BASE + ("index.html" if n == 0 else f"index_{n}.html"))
                except Exception: break
                got = parse_list(h)
                if not got: break
                items += got; time.sleep(0.5)
            if items: idx.write_text(json.dumps(items, ensure_ascii=False))
        except Exception as e: print("WARN 月报列表抓取失败，用缓存", e)
    if not items and idx.exists(): items = [tuple(x) for x in json.loads(idx.read_text())]
    recs = {}
    for y, mo, url, pub in items:
        f = RAW / f"{y}-{mo:02d}.html"
        if not f.exists():
            if offline: continue
            try: f.write_text(_get(url)); time.sleep(0.5)
            except Exception as e: print("WARN 跳过", url, e); continue
        d = parse_page(f.read_text())
        if len(d) >= 4: recs[(y, mo)] = {"ym": f"{y}-{mo:02d}", "url": url, "pub": pub, "d": d}
        else: print("WARN 月报解析失败", f)
    months = [recs[k] for k in sorted(recs)]
    return {"months": months, "source": "中国疾病预防控制中心 · 全国法定传染病疫情概况（月报）", "diseases": DISEASES}
