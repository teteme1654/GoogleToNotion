import streamlit as st
from outsource_calculation import write_to_google_sheets, update_notion_outsource_cost
from sync_sheets_to_notion import sync_sheets_to_notion
import tempfile
import json

# 🔐 secrets の読み込み（全スクリプト統一でst.secretsを使用）
NOTION_API_KEY = st.secrets["notion_token"]
PROJECT_DB_ID = st.secrets["project_db_id"]
OUTSOURCE_DB_ID = st.secrets["outsource_db_id"]
OUTSOURCE_SPREADSHEET_ID = st.secrets["outsource_spreadsheet_id"]
OUTSOURCE_SHEET_NAME = st.secrets["outsource_sheet_name"]

# Google認証情報を一時ファイルに保存
with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".json") as temp:
    temp.write(st.secrets["google_credentials_json"])
    GOOGLE_CREDENTIALS_FILE = temp.name
    

# ✅ UI タイトルと説明
st.set_page_config(page_title="C-cross", page_icon="📊")
st.title("📊 C-cross")
st.markdown("""
このツールでは、以下の機能を操作できます：
- Notion → Google Sheets への書き出し
- Google Sheets → Notion への反映
- 外注費の自動計算と反映
""")

st.markdown("---")

# ✅ 入力：スプレッドシート設定
with st.expander("📁 スプレッドシート設定", expanded=True):
    syncsheet_spreadsheet_id = st.text_input("スプレッドシートID", value="1IQnzuM9coZDDTF-3f9_GnZ3o06yIFX2d-_PikbN3On4")
    syncsheet_sheet_name = st.text_input("シート名", value="7月2025")

st.markdown("---")

# ✅ Google Sheets → Notion へ反映
with st.expander("👢 Google Sheets → Notion へ反映", expanded=False):
    if st.button("案件データ → Notionに反映"):
        try:
            sync_sheets_to_notion(syncsheet_sheet_name)
            st.success("✅ Notion DBに反映完了")
        except Exception as e:
            st.error(f"❌ エラー発生: {e}")

# ✅ Notion → Google Sheets
with st.expander("🧾 Notion → Google Sheets", expanded=False):
    if st.button("案件抽出（Notionから）"):
        try:
            write_to_google_sheets()
            st.success("✅ スプレッドシートへ書き込み完了")
        except Exception as e:
            st.error(f"❌ エラー発生: {e}")

# ✅ 外注費の反映（Notionへの最終更新）
with st.expander("💰 外注費の反映（最終ステップ）", expanded=False):
    if st.button("計算結果 → Notionに反映"):
        try:
            update_notion_outsource_cost(
                outsource_db_id=OUTSOURCE_DB_ID,
                notion_token=NOTION_API_KEY,
                project_db_id=PROJECT_DB_ID,
                outsource_spreadsheet_id=OUTSOURCE_SPREADSHEET_ID,
                outsource_sheet_name=OUTSOURCE_SHEET_NAME
            )
            st.success("✅ 外注費反映完了")
        except Exception as e:
            st.error(f"❌ エラー発生: {e}")
