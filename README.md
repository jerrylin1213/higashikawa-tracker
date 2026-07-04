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

- `未來 N 天入住率`（7/30/60/90）= 從明天起 N 晚中「不可訂」的比例。
- `今日新增預訂 / 今日取消` = 對比昨日快照，可訂↔已訂翻轉的晚數。
- `Booking 每晚均價` = Booking.com 參考房價（僅 Peak / perican 上架）。
- `預估營收60天` = 未來 60 天已訂晚數 × Booking 均價。
- `來源狀態 / Booking狀態 / 失敗詳情` = 每個來源當天抓取成敗，一眼看穿。
- niseu 逐棟（ペロ/チカプ/トゥンニ）各算一列；じゃらん/Airbnb 每間一列 → 共 7 個追蹤單位。

## Notion 結構（4 個 DB，parent page 底下自動建立）

- **每日紀錄** — 每天 × 每單位一列（入住率/房價/營收/新增·取消/來源狀態/失敗詳情）
- **90天行事曆** — 未來 90 天，逐日 × 7 單位房況 + 房價對照
- **真實入住歷史** — 逐夜實際房況，用「該夜前最後一次快照」判定（需快照累積）
- **入住彙總** — 各單位累積入住率

## 檔案

- `properties.py` — 5 間設定
- `airbnb_calendar.py` / `niseu_calendar.py` / `jalan_calendar.py` — 三種房況抓取器
- `prices.py` — Booking.com 房價（Peak / perican）
- `occupancy.py` — 入住率 / 已訂晚數 / 昨日 diff / 報價夜
- `tracker.py` — 主程式：抓取 → 計算 → 快照 → 寫 4 個 Notion DB
- `notion_sync.py` — 4 個 DB 的 find-or-create + 寫入
- `snapshots/<date>/<unit>.json` — 每日每單位原始快照（供 diff 與真實入住歷史）

## 本地測試

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python tracker.py dryrun   # 抓取+計算+快照，不寫 Notion
```

> 注意：Airbnb 密集本地呼叫會被 IP 限流（HTTP 400）；GitHub Actions 每天一次、每次新 runner IP，不受影響。

## 每日自動化

`.github/workflows/daily.yml` 每天 13:20 JST 執行：抓 5 間 → 算指標 → 寫 4 個 Notion DB。
需 `NOTION_TOKEN` + `NOTION_PARENT_PAGE_ID` 兩個 secret（未設時自動跳過 Notion、只存快照）。
