# 换季健康看板（cn-resp-weekly）

一个持续更新的单页仪表盘：**家庭版**（index.html）+ **专业版**（pro.html；旧地址 pharma.html 自动跳转），每周同一版式刷新；另有 RSS（feed.xml，每周一条 KPI 快照 + 分享卡）。静态站点，GitHub Pages 免费托管。

- 在线地址：https://tolsonhuddy-collab.github.io/cn-resp-weekly/
- 专业版：https://tolsonhuddy-collab.github.io/cn-resp-weekly/pro.html
- RSS：https://tolsonhuddy-collab.github.io/cn-resp-weekly/feed.xml

> 人群监测数据，不代表个人风险，不构成医疗建议。不推荐任何药品/品牌；疫苗表述仅引用疾控原文。

## 用法
```bash
python3 -m cnflu.scrape            # 抓取 CNIC 英文周报 PDF → raw/en/、raw/index.json（可断点续抓，404 跳过）
python3 -m cnflu.build             # 解析 → data/ → 多病原体合并 → site/
python3 -m cnflu.build --offline   # 只用 raw/ 缓存，不联网
python3 -m unittest discover -s tests
```
产物：`site/index.html`、`site/pro.html`、`site/feed.xml`、`site/cards/<周>.png`（最近30周）、`site/data/{weekly.csv,weekly.json,mp.json}`（页面可下载）。

## 数据来源
- 中国国家流感中心（CNIC）英文周报 PDF：ILI%、阳性率（全国/南/北）、亚型、暴发数。约 2020-W08 起；旧版日期格式（序数词、"week 20 (May 17th–May 23th 2021)"、原文日期笔误）已兼容；仍有约 11 周无法解析（2020 零星周、2021-W09/40/41、2025-W05 为图片 PDF），在 data 中标记 missing。
- 中国疾控中心哨点多病原体监测（自抓网页，门急诊/住院阳性率及官方较上周变化）。
- 更早的多病原体历史来自第三方整理 **cn_cdc_crawl**（GitHub 公开 CSV，页面与 README 均注明来源）；与自抓数据重叠部分逐值核对（当前 220 个值 0 不一致），不一致时以自抓为准并在构建时告警。

## 规则
- 流行季：每年 9 月 1 日起算；季周 =（周末日 − 9/1）// 7；图表横轴 9 月–3 月。
- 基线：往季同季周 ±1 周的值；2019-20（数据不全）、2020-21、2021-22（新冠防控期）不计入。
- 分位：基线中严格低于本周值的比例。<P25 低于往年，P25–P75 往年常见，>P75 高于往年。多病原体分位用 2024-11 以来全部周。
- 重点关注：分位>P75 且较上周上升者中涨幅最大；若无，取涨幅最大者（流感用往年同期分位）。
- 起始/峰值：先在季初 0–12 周找低谷；低谷后首次由 <10% 升至 ≥10% 为起始周，低谷后最大值为峰值；低谷仍 ≥10% 记“延续”（承接夏季波）。
- 所有变化箭头均为**较上周**。不做预测。

## Feed
每周一条，正文为该周 KPI 快照表（数值、较上周、等级/分位）+ 分享卡图；链接统一指向仪表盘（`#w2026-W42` 锚点），GUID 稳定为 `cn-resp-weekly-<年>-W<周>`，pubDate 为周报发布日期（缺失时用周末日）。

## 周选择与动效
- 家庭版顶部下拉选择最近 30 周（默认最新）；index.html 只内嵌最新一周，其余周按需 fetch `site/weeks/<年>-W<周>.json`（加载中提示；失败则停留当前周并提示）。支持 `index.html#w2026-W42` 锚点，feed 链接直达对应周。
- 本地预览需走 http：`cd site && python3 -m http.server`；直接用 file:// 打开时浏览器不允许 fetch，只能看最新一周。
- 网站动效（仅网页，feed 与分享卡完全静态）：曲线首次进入视口约 1 秒绘入（IntersectionObserver）、仅今季曲线有缓慢流光、各图最新点轻微脉冲。纯 CSS/SVG + 少量 JS，无第三方库；`prefers-reduced-motion` 时全部关闭。关闭方式：`cnflu/site.py` 设 `MOTION = False`，或给 `<html>` 加 `class="no-motion"`。

## AI 解读（BYOK，可选）
页面底部面板：用户自填 DeepSeek key，仅存本机浏览器 localStorage，由浏览器直接请求 `api.deepseek.com`（已确认 CORS 允许），提示词只含本页数据，并禁止编造、预测、医疗建议与药品。构建过程不调用任何 LLM、不读取环境变量中的密钥。

## 发布与自动更新
- `cnflu/site.py` 的 `SITE_URL` 已设为线上地址（feed 链接、GUID 锚点、分享卡图均为绝对地址）。
- GitHub Actions（`.github/workflows/build.yml`）：每周四、周五 UTC 10:00（日本时间 19:00）及手动触发；在线构建（抓 CNIC、中国疾控、法定传染病月报、Open-Meteo），任一数据源不可达时沿用缓存、不清空数据；测试通过后仅在有变化时提交 data/site，并部署 `site/` 到 GitHub Pages。
- 原始 PDF（约 143MB）不入库；入库的是解析结果小缓存 `raw/en/*.parsed.json` 与元数据 `raw/en/*.json`，离线/增量构建无需 PDF。

## 常见传染病（月报）与降温提醒（家庭版底部，不随周选择切换）
- 月报：`cnflu/notif.py` 抓中国疾控「全国法定传染病疫情概况」列表（jksj01 index.html/index_1/index_2），缓存 `raw/notif/`，输出 `data/notif.json`。现有 2024年1月 – 2026年8月共 32 月。
  - 呼吸道传播：流感、百日咳、猩红热、流行性腮腺炎、麻疹、风疹、肺结核、人感染新亚型流感；手足口病单列为「肠道病毒（非呼吸道）」。
  - 卡片：当月报告发病数、较上月、近24月曲线、往年同月范围（灰带）。只列数字。
  - Feed：周报发布日前 7 天内有新月报时，加一行「新月报」。
- 降温提醒：`cnflu/temp.py`，Open-Meteo（不需要 key），6 城，只取构建日前的 7 天（不含今天，不含预报），缓存 `raw/temp.json`。
  - 降温定义：当日最低气温比前一日低 ≥8℃。气温日期区间与流感周报周次分别标注。
- `--offline` 构建时，两者都读缓存。
