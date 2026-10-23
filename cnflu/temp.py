"""降温提醒：Open-Meteo 过去 7 天日最高/最低气温（仅历史，不含预报）。"""
import json, urllib.request, pathlib, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "raw" / "temp.json"
CITIES = [("北京", 39.90, 116.40), ("上海", 31.23, 121.47), ("广州", 23.13, 113.26),
          ("成都", 30.57, 104.07), ("哈尔滨", 45.80, 126.53), ("武汉", 30.59, 114.31)]
DROP = 8.0  # 定义：当日最低气温较前一日最低气温下降 ≥8℃
SOURCE = "Open-Meteo（open-meteo.com，CC BY 4.0）"

def drops(tmin, thr=DROP):
    """返回下标 i（i≥1），满足 tmin[i-1]-tmin[i] ≥ thr。"""
    return [i for i in range(1, len(tmin)) if tmin[i] is not None and tmin[i-1] is not None and tmin[i-1] - tmin[i] >= thr - 1e-9]

def _fetch(lat, lon):
    u = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
         "&daily=temperature_2m_max,temperature_2m_min&past_days=8&forecast_days=1&timezone=Asia%2FShanghai")
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "cn-resp-weekly"}), timeout=30) as r:
        return json.loads(r.read())["daily"]

def build(offline=False, today=None):
    today = today or dt.date.today().isoformat()
    if not offline:
        try:
            out = {"built": today, "cities": []}
            for n, la, lo in CITIES:
                d = _fetch(la, lo)
                # 只保留今天之前的日期（过去 7 天 + 前一日用于比较）
                rows = [(t, a, b) for t, a, b in zip(d["time"], d["temperature_2m_max"], d["temperature_2m_min"]) if t < today][-8:]
                out["cities"].append({"name": n, "date": [r[0] for r in rows], "tmax": [r[1] for r in rows], "tmin": [r[2] for r in rows]})
            CACHE.write_text(json.dumps(out, ensure_ascii=False))
        except Exception as e: print("WARN 气温抓取失败，用缓存", e)
    if not CACHE.exists(): return None
    out = json.loads(CACHE.read_text())
    for c in out["cities"]: c["drops"] = [i for i in drops(c["tmin"]) if i >= 1]
    out["source"] = SOURCE; out["thr"] = DROP
    return out
