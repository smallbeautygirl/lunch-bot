# lunch-bot 🍱

每個上班日 11:00，在 Teams 群組「午餐好夥伴」推 3 家午餐候選，由午餐長拍板。

## 它會做什麼

| 哪天 | 發什麼 |
|---|---|
| 上班日（週一到週五、補班日） | 今日幸運星座運勢、3 家候選店、tag 午餐長、一則附加內容 |
| 國定假日（平日放假） | 英文一句 + 笑話，不挑店也不 tag 人 |
| 週末 | 不發 |

- **店家**來自 [Linker Vision Lunch Map](https://lunch-map.betoolman.com/) 的 `/api/shops`。只挑 11:40 有營業、開車 15 分鐘內、價位 500 元以下（價位不明也算）、可內用或外帶、最近 5 個推薦日沒出現過的店。營業時間不明的店不推。
- **走路還是開車**：用網站本身 `/api/config` 的門檻和停車場資料來算，結果和網站一致。
- **星座**：每天隨機一個。Claude 寫運勢，並挑出「今天適合」的店家分類。3 家裡有 2 家依運勢加權，1 家完全隨機。
- **附加內容**（Claude 產生）：一和五是笑話，二和四是英文，三是冷知識。
- 同一天重跑，挑出的店相同（以日期當亂數種子）。
- 午餐地圖連不上時，改用上一次成功抓到的資料（存在 Actions cache，不進 repo）。
- Claude 呼叫失敗或沒設定 key 時，照樣發出挑店結果，只是少了運勢和附加內容。

## 設定

1. **Teams**：在「午餐好夥伴」聊天室 → `…` → Workflows → 選「Send webhook alerts to a chat」範本，建立後複製 webhook URL。
2. **GitHub Secrets**（Settings → Secrets and variables → Actions）：
   - `TEAMS_WEBHOOK_URL`：上一步的 URL
   - `ANTHROPIC_API_KEY`：專用、有消費上限的 key
   - `LUNCH_CHIEF_EMAIL`：午餐長的 Teams 帳號 email（放 secret，不寫進公開 repo）
3. **GitHub Variables**（選填）：`LUNCH_CHIEF_NAME`，卡片上 tag 顯示的名字，預設「午餐長」。
4. 到 Actions → Lunch bot → Run workflow，勾著 `dry_run` 跑一次，在 log 裡看卡片內容。取消勾選再跑一次，就會真的發到群組。

排程是 `0 3 * * *`（台北 11:00）。GitHub 的排程常會延遲幾分鐘到十幾分鐘。

## 本機開發

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/python -m lunch_bot.main --dry-run --date 2026-11-09
```

台灣假日資料來自 [ruyut/TaiwanCalendar](https://github.com/ruyut/TaiwanCalendar)（政府行政機關辦公日曆）。
