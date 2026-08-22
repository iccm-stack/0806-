# 全球 AI 科技情報週報

每週自動收集全球 AI 第一手資訊與高品質來源，經過去重、重要性評分與深度分析後，產生：

- GitHub 完整 Markdown 週報
- Email 5～10 分鐘精華版
- 可供下週比較的歷史趨勢狀態

排程固定於每週一上午 10:00（Asia/Taipei）執行。系統只選真正重要的 5～10 件事，不為湊數收錄一般新聞。

## 工作方式

1. 收集 Tier 1 官方／原始研究、Tier 2 延伸來源與 arXiv 候選。
2. 先以 URL 與標題做確定性去重。
3. 使用 Groq 對候選批次評分，技術突破與研究新穎性權重最高。
4. 以跨週 `event_key` 排除已完整分析的舊事件。
5. 對 Top 5～10 進行技術＋商業分析，重大突破升級為深度技術分析。
6. 找出 1～3 個跨事件趨勢，與前四週比較，提出 6～24 個月的條件式展望。
7. 寫入 `reports/YYYY/YYYY-MM-DD.md`，更新 `data/state.json`，並寄送 Email 精華。

任一來源暫時失效只會留下 warning，不會讓其他來源一起失敗；若完全沒有候選，系統會停止而不是寄出空週報。

## 安全與 Groq 設定

Groq API key **只**從環境變數 `GROQ_API_KEY` 讀取，不會寫入程式、設定檔或報告。

- Model 固定為 `llama-3.3-70b-versatile`
- 每次 Groq HTTP request 固定帶 `User-Agent`
- `.env` 已列入 `.gitignore`
- GitHub Actions 使用 Repository Secrets

## 啟用 GitHub Actions

到 repo 的 **Settings → Secrets and variables → Actions** 新增：

必要 Secret：

- `GROQ_API_KEY`

若要寄 Email，再新增：

- `SMTP_HOST`，例如 `smtp.gmail.com`
- `SMTP_PORT`，SSL 通常為 `465`；STARTTLS 通常為 `587`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`（Gmail 請使用 App Password，不要使用帳號主密碼）
- `EMAIL_FROM`（可省略，預設同 `SMTP_USERNAME`）
- `EMAIL_TO`

若 SMTP 尚未設定，完整 Markdown 仍會正常產生，只跳過寄信。

Actions 的 cron 使用 UTC，因此設定為週一 `02:00 UTC`，等同台北時間週一 10:00。也可在 Actions 頁手動執行 `Generate Global AI Weekly` 驗收。

## 本機執行

需要 Python 3.11 以上：

```bash
python -m venv .venv
python -m pip install --no-build-isolation -e .
```

設定環境變數後執行：

```bash
ai-weekly --root . --no-email
```

執行測試：

```bash
python -m unittest discover -s tests -v
```

## 來源維護

來源集中在 `config/sources.json`。每個 feed 可設定：

- `tier`: `1` 為核心來源、`2` 為延伸來源
- `kind`: `official`、`original_research` 或 `high_quality_media`

來源品質優先順序固定為「官方／原始研究 > 高品質媒體 > 專業社群」。社群熱門度只適合作為探索訊號，不能直接當成已確認事實。

## 目前邊界

- 第一版以公開 RSS/Atom 與 arXiv 為穩定核心，避免依賴付費新聞或搜尋 API。
- 報告是決策輔助，不是事實資料庫；重大決策仍應閱讀每則事件附上的原始連結。
- GitHub Actions 的排程可能因平台負載延後數分鐘，但排程時區換算固定正確。
