"""抓取 CNIC 英文周报列表与 PDF（体积约 0.3MB，中文版约 5MB），本地缓存，礼貌限速。"""
import json, re, time, pathlib, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36 cn-flu-weekly/0.1"
BASE = "https://ivdc.chinacdc.cn/cnic/en/Surveillance/WeeklyReport/"
ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "en"
DELAY = 2.0

def get(url, binary=False, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                b = r.read()
            time.sleep(DELAY)
            return b if binary else b.decode("utf-8", "replace")
        except Exception as e:
            print("retry", url, e); time.sleep(5 * (i + 1))
    raise RuntimeError(url)

def list_reports(min_year=2019, min_week=35, max_pages=60):
    out = []
    for p in range(max_pages):
        url = BASE + ("index.htm" if p == 0 else f"index_{p}.htm")
        try: html = get(url)
        except RuntimeError: break
        items = re.findall(r'<a href="\./(\d{6}/t\d+_\d+\.htm)"[^>]*>\s*Week\s*(\d+)\s*(\d{4})\s*</a>\s*(?:<[^>]+>\s*)*\(?(\d{2}-\d{2})?', html)
        if not items: break
        stop = False
        for path, wk, yr, md in items:
            wk, yr = int(wk), int(yr)
            if (yr, wk) < (min_year, min_week): stop = True; continue
            out.append({"year": yr, "week": wk, "detail_url": BASE + path})
        if stop: break
    return out

def fetch_pdf(rep):
    f = RAW / f"{rep['year']}-W{rep['week']:02d}.pdf"
    meta = RAW / f"{rep['year']}-W{rep['week']:02d}.json"
    if f.exists() and meta.exists():
        rep.update(json.loads(meta.read_text())); return f
    html = get(rep["detail_url"])
    m = re.search(r'href="\./(P\d+\.pdf)"', html)
    if not m: print("no pdf", rep); return None
    pdf_url = rep["detail_url"].rsplit("/", 1)[0] + "/" + m.group(1)
    pm = re.search(r'(\d{4}-\d{2}-\d{2})', html)
    f.write_bytes(get(pdf_url, binary=True))
    rep.update({"pdf_url": pdf_url, "page_date": pm.group(1) if pm else None})
    meta.write_text(json.dumps({k: rep[k] for k in ("pdf_url", "page_date")}))
    return f

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    reps = list_reports()
    print(len(reps), "reports listed")
    (ROOT / "raw" / "index.json").write_text(json.dumps(reps, ensure_ascii=False, indent=1))
    for r in reps:
        try: fetch_pdf(r)
        except Exception as e: print("跳过", r["year"], r["week"], e)
    (ROOT / "raw" / "index.json").write_text(json.dumps(reps, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
