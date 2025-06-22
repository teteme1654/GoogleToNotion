import streamlit as st
from outsource_calculation import write_to_google_sheets, update_notion_outsource_cost
from sync_sheets_to_notion import sync_sheets_to_notion
import tempfile
import json

# 🔐 secrets の読み込み
NOTION_API_KEY = st.secrets["notion_token"]
PROJECT_DB_ID = st.secrets["project_db_id"]
OUTSOURCE_DB_ID = st.secrets["outsource_db_id"]

# 一時ファイルとしてGoogle認証情報を保存
with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".json") as temp:
    temp.write(st.secrets["google_credentials_json"])
    GOOGLE_CREDENTIALS_FILE = temp.name

st.title("📊 Notion × Google Sheets 同期ツール")

st.markdown("---")

# ✅ 入力：スプレッドシート設定
st.subheader("📁 スプレッドシート設定")
spreadsheet_id = st.text_input("スプレッドシートID", value="1L5t1VZFF_jYjQP9PDvoF9_3KBXQW_6qTf58qsZ8RJ7A")
sheet_name = st.text_input("シート名", value="GTN_外注DB計算シート")

st.markdown("---")

# ✅ 案件抽出ボタン（スプレッドシート → Notion登録用）
st.subheader("🗂 スプレッドシート → Notionへ反映")
if st.button("案件データ → Notionへ反映"):
    try:
        sync_sheets_to_notion(
            spreadsheet_id,
            sheet_name,
            GOOGLE_CREDENTIALS_FILE,
            NOTION_API_KEY,
            PROJECT_DB_ID
        )
        st.success("✅ Notion DBに反映完了")
    except Exception as e:
        st.error(f"❌ エラー発生: {e}")

# ✅ スプシ反映ボタン（Notion → スプシ用）
st.subheader("🧾 Notion → スプレッドシート")
if st.button("案件抽出（Notionから）"):
    try:
        write_to_google_sheets(
            GOOGLE_CREDENTIALS_FILE,
            NOTION_API_KEY,
            PROJECT_DB_ID,
            OUTSOURCE_DB_ID,
            spreadsheet_id,
            sheet_name
        )
        st.success("✅ スプレッドシートへ書き込み完了")
    except Exception as e:
        st.error(f"❌ エラー発生: {e}")

# ✅ 計算結果反映ボタン（料金 → Notion外注費反映用）
st.subheader("💰 外注費の最終反映")
if st.button("計算結果 → Notion反映"):
    try:
        update_notion_outsource_cost(
            GOOGLE_CREDENTIALS_FILE,
            NOTION_API_KEY,
            PROJECT_DB_ID,
            spreadsheet_id,
            sheet_name
        )
        st.success("✅ 外注費反映完了")
    except Exception as e:
        st.error(f"❌ エラー発生: {e}")
