# GoogleToNotion / C-cross

GoogleスプレッドシートとNotionを連携するツール。StreamlitのUIから操作する。

---

## 概要

| 機能 | 内容 |
|---|---|
| スケジュール表 → Notion | Googleスプレッドシートの案件スケジュールをNotionプロジェクトDBに登録・更新 |
| Notion → 外注DB計算シート | 請求済みプロジェクトの外注スタッフ情報をGoogleスプレッドシートに書き出し |
| 外注費 → Notion反映 | スプレッドシートで確定した外注費をNotionの外注費プロパティに反映 |

## データフロー

```
スケジュール表（Google Sheets）
        ↓ sync_sheets_to_notion.py
Notion プロジェクトDB
        ↓ outsource_calculation.py
GTN_外注DB計算シート（Google Sheets）※金額を手動修正
        ↓ GAS → Flask API (/update_notion_outsource_cost)
Notion プロジェクトDB（外注費プロパティ）
```

---

## ファイル構成

```
.
├── streamlit_ui.py          # StreamlitのUI（操作画面）
├── sync_sheets_to_notion.py # スケジュール表 → Notion
├── outsource_calculation.py # 外注費計算・Notion/Sheets連携
├── api.py                   # Flask API（GASから呼び出し）
├── app.py                   # Render用WSGIエントリポイント
├── render_start.py          # Render本番起動スクリプト
├── render.yaml              # Renderサービス設定
├── Procfile                 # Streamlit起動設定
└── requirements.txt
```

---

## Secrets設定（RenderのSecret Files）

`.streamlit/secrets.toml` に以下を設定する。

```toml
notion_token               = "secret_..."
project_db_id              = "..."         # NotionプロジェクトDB
outsource_db_id            = "..."         # Notion外注DB
syncsheet_spreadsheet_id   = "..."         # スケジュール表のスプレッドシートID
outsource_spreadsheet_id   = "..."         # GTN_外注DB計算シートのスプレッドシートID
outsource_sheet_name       = "..."         # 外注DB計算シートのシート名
google_credentials_json    = '''{ ... }''' # サービスアカウントのJSONキー（丸ごと貼り付け）
```

> **NotionのDB IDの確認方法**
> DBをフルページで開いたときのURL `https://www.notion.so/XXXXXXXX?v=...` の `?v=` より前の部分。

---

## Googleサービスアカウントの権限設定

新しいスプレッドシートを使う場合は、`google_credentials_json` 内の `client_email` をそのスプレッドシートの共有メンバーに追加すること（編集者権限）。これを忘れると権限エラーになる。

---

## 年度切り替え手順

1. **secrets.tomlを更新**（Renderダッシュボード → 対象サービス → Environment → Secret Files）
   - `syncsheet_spreadsheet_id`：新年度のスケジュール表IDに変更
   - `outsource_sheet_name`：新年度のシート名に変更
2. **新しいスプレッドシートにサービスアカウントを共有追加**
3. **Renderで再デプロイ**（Manual Deploy → Deploy latest commit）
4. `streamlit_ui.py` の月ドロップダウンのハードコード年度を更新してコミット
   ```python
   # streamlit_ui.py 該当箇所
   _months = [f"{m}月2026" for m in range(4, 13)] + [f"{m}月2027" for m in range(1, 4)]
   ```

---

## デプロイ（Render）

- サービス名：`google-to-notion`
- ダッシュボード：https://dashboard.render.com
- ログ確認：Logsタブ → Runtime ログ
- キャッシュ再構築が必要な場合：Manual Deploy → Clear build cache & deploy

---

## ローカル開発

```bash
git clone https://github.com/kei.gtdr/GoogleToNotion
cd GoogleToNotion
pip install -r requirements.txt

# .streamlit/secrets.toml を作成してsecretsを設定
streamlit run streamlit_ui.py
```
