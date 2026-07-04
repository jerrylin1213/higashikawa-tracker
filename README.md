# higashikawa-tracker

每日追蹤 **東川町 5 間競品民宿**的入住率（未來 7/30/60/90 天），寫入 Notion。
對標自家 villa-tracker（東川自家 3 棟），邏輯仿 maruko-tracker，獨立運作。

## 追蹤對象與資料來源（phase 1）

平台四散，用 3 種抓法混合：

| 標籤 | 來源 | ID / URL | 房況粒度 |
| --- | --- | --- | --- |
| The Peak Villa Suite | Airbnb calendar API | 37946397 | 單一 listing |
| クレインハウス Crane | Airbnb calendar API | 36903070 | 單一 listing |
| Villa ニセウコロコロ | 官網空室日曆 | nisew-corocoro.com/calendar/ | 逐日 × 3 棟（ペロ/チカプ/トゥンニ）|
| 東川ペリカン Pelican | じゃらん空室カレンダー | yad398511 | 設施層級（有無空房）|
| andon 行灯 | じゃらん空室カレンダー | yad373749 | 設施層級（有無空房）|

- **Airbnb**：公開 `PdpAvailabilityCalendar` GraphQL，純標準庫、零維護、~122 天。價格永遠 null（登入牆）。
- **niseu 官網**：JS grid 日曆，Playwright 渲染後解析「日期 + 3 棟 ○/×」，~87 天，粒度比 Airbnb 還細。
- **じゃらん**：Playwright 渲染月曆（×=満室、N部屋/○=有房），用 `stayYear/stayMonth` 翻月，~116 天。設施層級（andon 5 房只要 1 房空就算有房）。

> 之後可擴：mizuki、Gallery Stay（樂天/Yahoo 房況，較費工）、The Garnet、Piano&Stay（只有房價）。

## 指標

- `未來 N 天入住率` = 從明天起 N 晚中「不可訂」的比例。
- niseu 逐棟各算一列；じゃらん/Airbnb 每間一列。

## 檔案

- `properties.py` — 5 間設定
- `airbnb_calendar.py` / `niseu_calendar.py` / `jalan_calendar.py` — 三種抓取器
- `occupancy.py` — forward occupancy 計算
- `tracker.py` — 主程式：抓取 → 計算 → 快照 →（Notion，phase 2）
- `snapshots/<date>/` — 每日原始快照 + occupancy

## 本地測試

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python tracker.py dryrun   # 抓取+計算+快照，不寫 Notion
```

> 注意：Airbnb 密集本地呼叫會被 IP 限流（HTTP 400）；GitHub Actions 每天一次、每次新 runner IP，不受影響。

## 每日自動化

`.github/workflows/daily.yml` 每天 13:20 JST 執行。phase 1 先跑 `dryrun`（驗證抓取）；
Notion 設定完成後改為寫入模式並加 `NOTION_TOKEN` secret（phase 2）。
