# lunch-bot 🍱

在 Teams 群組「午餐好夥伴」每個上班日發兩則訊息：

- **09:10 早安卡**：股市快照＋群組成員星座的今日運勢
- **11:00 午餐卡**：3 家午餐候選，由午餐長拍板

## 09:10 早安卡

只在上班日（含補班）發，國定假日和週末不發（休市日只會重複上個交易日的數字）。

- **台股**：加權指數，抓 Yahoo Finance 當下的數字並標時間。開盤中寫「截至 09:14」，還沒開盤就寫「11/5 收盤」。卡片是發送當下的快照，不會自己更新；想看最新的盤點「看即時盤」。
- **隔夜美股**：S&P 500、那斯達克、費城半導體、台積電 ADR 的前一晚收盤。
- **星座運勢**（Claude 產生，僅供娛樂）：只列群組裡有人的星座，每個星座附上成員名字、一兩句運勢、財運 ★1–5、幸運色，最後標出今日財運最旺的星座。不 tag 任何人。運勢以[唐陽雞酒屋](https://podcasts.apple.com/tw/podcast/id1536374746) podcast 每週一發的「唐綺陽星座運勢週報」為底（從 RSS 節目說明讀出每個星座本週是累的／穩的／讚的，和一句工作、感情方向），由 Claude 換成當天的上班族情境，卡片上標出本週分級並附該集連結；不照抄原句，也禁止星座刻板印象和咖啡梗。週報約週一 11:00 才發，所以週一早上（和抓不到時）只靠 Claude。
- 股市或 Claude 失敗時，該段改顯示「暫時抓不到」，其餘照發。

## 11:00 午餐卡

| 哪天 | 發什麼 |
|---|---|
| 上班日（週一到週五、補班日） | 今日幸運星座運勢、3 家候選店、tag 午餐長、一則附加內容 |
| 國定假日（平日放假） | 英文單字 + 笑話，不挑店也不 tag 人 |
| 週末 | 不發 |

- **店家**來自 [Linker Vision Lunch Map](https://lunch-map.betoolman.com/) 的 `/api/shops`。只挑 11:40 有營業、開車 15 分鐘內、價位 500 元以下（價位不明也算）、可內用或外帶、最近 5 個推薦日沒出現過的店。營業時間不明的店不推。
- **走路還是開車**：用網站本身 `/api/config` 的門檻和停車場資料來算，結果和網站一致。
- **停車**：開車去的店下面加一行，列 300m 內最近、還有空位的路外停車場和路邊停車路段（距離、費率、剩餘車位），資料是交通部 [TDX](https://tdx.transportdata.tw/) 的高雄即時停車資料，需要 `TDX_CLIENT_ID`／`TDX_CLIENT_SECRET` secrets；剩餘車位是發卡當下（約 10:50）的數字，只供參考。沒設金鑰或 TDX 連不上時就不顯示。
- **星座**：每天從群組成員的星座裡隨機抽一個，並列出是誰的星座（沒設定成員名單時從 12 星座抽）。Claude 寫運勢，並挑出「今天適合」的店家分類。3 家裡有 2 家依運勢加權，1 家完全隨機。
- **股市**：加權指數漲 ≥0.3% 是「加菜」日，3 家都從 $$ 以上的店挑；跌 ≥0.3% 是「省一點」日，3 家都從 $ 的店挑；平盤不限。價位不明的店看分類（牛排、海鮮、火鍋算貴，便當、小吃、麵等算平價）。符合的店不夠 3 家才從其他店補。數字抓自 Yahoo Finance，盤中標「截至 11:05」。
- **附加內容**（Claude 產生）：一和五是笑話，二和四是英文，三是冷知識。笑話和英文日改用 Sonnet（Haiku 寫的中文諧音常對不上）：笑話附台灣經典冷笑話當範例，並附一段一本正經的「笑點解析」；英文是中高級單字配中文諧音記憶法（例：kangaroo 袋鼠 →「看個路」）和一句例句。
- 同一天重跑，挑出的店相同（以日期當亂數種子）。
- 午餐地圖連不上時，改用上一次成功抓到的資料（存在 Actions cache，不進 repo）。
- Claude 呼叫失敗或沒設定 key 時，照樣發出挑店結果，只是少了運勢和附加內容。

## 設定

1. **Teams**：在「午餐好夥伴」聊天室 → `…` → Workflows → 選「Send webhook alerts to a chat」範本，建立後複製 webhook URL。
2. **GitHub Secrets**（Settings → Secrets and variables → Actions）：
   - `TEAMS_WEBHOOK_URL`：上一步的 URL
   - `ANTHROPIC_API_KEY`：專用、有消費上限的 key
   - `LUNCH_CHIEF_EMAIL`：午餐長的 Teams 帳號 email（放 secret，不寫進公開 repo）
   - `GROUP_MEMBERS`：星座 → 成員名字的 JSON，例如 `{"牡羊": ["amy", "bob"], "水瓶座": ["carol"]}`（星座寫不寫「座」都可以）。放 secret 是因為 repo 公開；Actions log 也公開，所以程式會把每個名字遮蔽（`::add-mask::`），dry run 印出的卡片看不到名字。
3. **GitHub Variables**（選填）：`LUNCH_CHIEF_NAME`，卡片上 tag 顯示的名字，預設「午餐長」。
4. 到 Actions → Lunch bot（或 Morning horoscope）→ Run workflow，勾著 `dry_run` 跑一次，在 log 裡看卡片內容。取消勾選再跑一次，就會真的發到群組。

排程由維護者開發機上的 crontab 負責：每天台北 09:10、10:50（UTC `10 1`、`50 2`）各跑一次 `gh workflow run <morning|lunch>.yml --ref main -f dry_run=false -f post_for_real=true`。GitHub 自己的 `schedule` 在 2026-11-07～09 連續晚了 6 小時以上才跑，所以不用。機器關機那天就不會發，需要時到 Actions 手動 Run workflow（取消 `dry_run`、勾 `post_for_real`）補發。週末、假日由程式自己跳過；開跑太晚（早安卡過 10:30、午餐卡過 11:45）也會跳過不發。

## 本機開發

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/python -m lunch_bot.main --dry-run --date 2026-11-09
.venv/bin/python -m lunch_bot.morning --dry-run --date 2026-11-09
```

台灣假日資料來自 [ruyut/TaiwanCalendar](https://github.com/ruyut/TaiwanCalendar)（政府行政機關辦公日曆）。
