import streamlit as st
from outsource_calculation import write_to_google_sheets, update_notion_outsource_cost
from sync_sheets_to_notion import (
    sync_sheets_to_notion,
    sync_log,
    update_log,
    read_sheet_data,
    _clean_secret,
)
import tempfile
import json

# secrets の読み込み（全スクリプト統一でst.secretsを使用）
NOTION_API_KEY = st.secrets["notion_token"]
PROJECT_DB_ID = st.secrets["project_db_id"]
OUTSOURCE_DB_ID = st.secrets["outsource_db_id"]
OUTSOURCE_SPREADSHEET_ID = st.secrets["outsource_spreadsheet_id"]
OUTSOURCE_SHEET_NAME = st.secrets["outsource_sheet_name"]

# Google認証情報を一時ファイルに保存
with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".json") as temp:
    temp.write(st.secrets["google_credentials_json"])
    GOOGLE_CREDENTIALS_FILE = temp.name


# UI タイトルと説明
st.set_page_config(page_title="C-cross", page_icon="📊")
st.title("📊 C-cross")
st.markdown("""
このツールでは、以下の機能を操作できます：
- Notion → Google Sheets への書き出し
- Google Sheets → Notion への反映
- 外注費の自動計算と反映
""")

st.markdown("---")

# 入力：スプレッドシート設定
with st.expander("📁 スプレッドシート設定", expanded=True):
    syncsheet_spreadsheet_id = st.text_input("スプレッドシートID", value="1IQnzuM9coZDDTF-3f9_GnZ3o06yIFX2d-_PikbN3On4")
    _months = [f"{m}月2026" for m in range(4, 13)] + [f"{m}月2027" for m in range(1, 4)]
    syncsheet_sheet_name = st.selectbox("シート名", _months)

st.markdown("---")

# --- session_state 初期化 ---
if "sync_phase" not in st.session_state:
    st.session_state.sync_phase = "idle"
if "match_candidates" not in st.session_state:
    st.session_state.match_candidates = []
if "existing_options" not in st.session_state:
    st.session_state.existing_options = []
if "project_entries" not in st.session_state:
    st.session_state.project_entries = None
if "preview_sheet_name" not in st.session_state:
    st.session_state.preview_sheet_name = None

# Google Sheets → Notion へ反映（3フェーズUI）
with st.expander("👢 Google Sheets → Notion へ反映", expanded=True):

    # ========== Phase 1: idle ==========
    if st.session_state.sync_phase == "idle":
        if st.button("プレビュー（名寄せチェック）"):
            with st.spinner("シート読み込み中..."):
                try:
                    project_entries, fiscal_year_start = read_sheet_data(syncsheet_sheet_name)
                    st.session_state.project_entries = project_entries
                    st.session_state.preview_sheet_name = syncsheet_sheet_name

                    # シートからクライアント名を抽出
                    incoming_clients = set()
                    for (_, client_name) in project_entries.keys():
                        if client_name:
                            incoming_clients.add(client_name)

                    # Notionの既存オプションを取得
                    from notion_client import Client
                    from name_matching import (
                        get_existing_select_options,
                        find_new_values,
                        match_names_with_claude,
                    )

                    notion = Client(auth=_clean_secret(st.secrets["notion_token"]))
                    db_id = _clean_secret(st.secrets["project_db_id"])
                    existing_options = get_existing_select_options(notion, db_id, "クライアント名")
                    st.session_state.existing_options = existing_options

                    # 新しい値を検出
                    new_values = find_new_values(list(incoming_clients), existing_options)

                    if not new_values:
                        # 新しい値がない → 直接同期
                        st.info("新しいクライアント名はありません。直接同期します。")
                        sync_log.clear()
                        update_log.clear()
                        sync_sheets_to_notion(syncsheet_sheet_name)
                        st.success("Notion DBに反映完了")
                        if sync_log:
                            st.write("🆕 新規追加:", sync_log)
                        if update_log:
                            st.write("🔄 更新:", update_log)
                    else:
                        # Claude で名寄せ判定
                        with st.spinner("Claude APIで名寄せ判定中..."):
                            candidates = match_names_with_claude(new_values, existing_options)

                        if candidates is None:
                            # API利用不可 → フォールバック（従来動作）
                            st.warning("Claude APIが利用できません。名寄せチェックなしで同期します。")
                            sync_log.clear()
                            update_log.clear()
                            sync_sheets_to_notion(syncsheet_sheet_name)
                            st.success("Notion DBに反映完了")
                            if sync_log:
                                st.write("🆕 新規追加:", sync_log)
                            if update_log:
                                st.write("🔄 更新:", update_log)
                        else:
                            st.session_state.match_candidates = candidates
                            st.session_state.sync_phase = "preview"
                            st.rerun()

                except Exception as e:
                    st.error(f"エラー発生: {e}")

        st.markdown("---")
        st.caption("または名寄せチェックなしで直接同期:")
        if st.button("直接同期（名寄せスキップ）"):
            try:
                sync_log.clear()
                update_log.clear()
                sync_sheets_to_notion(syncsheet_sheet_name)
                st.success("Notion DBに反映完了")
                if sync_log:
                    st.write("🆕 新規追加:", sync_log)
                if update_log:
                    st.write("🔄 更新:", update_log)
            except Exception as e:
                st.error(f"エラー発生: {e}")

    # ========== Phase 2: preview ==========
    elif st.session_state.sync_phase == "preview":
        st.subheader("名寄せ候補の確認")
        st.markdown("以下のクライアント名がNotionに存在しません。既存の値に統合するか確認してください。")

        candidates = st.session_state.match_candidates
        existing_options = st.session_state.existing_options

        user_decisions = {}

        for i, candidate in enumerate(candidates):
            new_val = candidate["new_value"]
            suggested = candidate.get("suggested_match")
            confidence = candidate.get("confidence", 0)
            reason = candidate.get("reason", "")

            st.markdown(f"### `{new_val}`")
            if suggested:
                conf_pct = f"{confidence:.0%}"
                st.markdown(f"推奨マッチ: **{suggested}** （確信度: {conf_pct}）")
                st.caption(f"理由: {reason}")

            # デフォルト選択: 確信度 >= 0.7 なら統合、それ以外は新規
            options = ["既存値に統合", "新規として追加", "手動で選択"]
            default_idx = 0 if (suggested and confidence >= 0.7) else 1

            choice = st.radio(
                f"「{new_val}」の処理",
                options,
                index=default_idx,
                key=f"choice_{i}",
                horizontal=True,
            )

            if choice == "既存値に統合":
                if suggested:
                    user_decisions[new_val] = suggested
                else:
                    # suggestedがない場合は手動選択にフォールバック
                    selected = st.selectbox(
                        f"「{new_val}」の統合先を選択",
                        existing_options,
                        key=f"manual_fallback_{i}",
                    )
                    user_decisions[new_val] = selected
            elif choice == "新規として追加":
                user_decisions[new_val] = None  # マッピングなし
            elif choice == "手動で選択":
                selected = st.selectbox(
                    f"「{new_val}」の統合先を選択",
                    existing_options,
                    key=f"manual_{i}",
                )
                user_decisions[new_val] = selected

            st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("確定してSync実行", type="primary"):
                # マッピング構築（Noneは除外）
                name_mapping = {k: v for k, v in user_decisions.items() if v is not None}
                st.session_state.sync_phase = "confirmed"
                st.session_state.name_mapping = name_mapping
                st.rerun()
        with col2:
            if st.button("キャンセル"):
                st.session_state.sync_phase = "idle"
                st.session_state.match_candidates = []
                st.session_state.project_entries = None
                st.rerun()

    # ========== Phase 3: confirmed ==========
    elif st.session_state.sync_phase == "confirmed":
        name_mapping = st.session_state.get("name_mapping", {})
        sheet_name = st.session_state.get("preview_sheet_name", syncsheet_sheet_name)

        with st.spinner("Notionに同期中..."):
            try:
                sync_log.clear()
                update_log.clear()
                sync_sheets_to_notion(sheet_name, name_mapping=name_mapping or None)
                st.success("Notion DBに反映完了")

                if name_mapping:
                    st.info("適用された名寄せ:")
                    for old, new in name_mapping.items():
                        st.write(f"  {old} → {new}")

                if sync_log:
                    st.write("🆕 新規追加:", sync_log)
                if update_log:
                    st.write("🔄 更新:", update_log)
            except Exception as e:
                st.error(f"エラー発生: {e}")

        # リセット
        st.session_state.sync_phase = "idle"
        st.session_state.match_candidates = []
        st.session_state.project_entries = None
        st.session_state.name_mapping = {}

# Notion → Google Sheets
with st.expander("🧾 Notion → Google Sheets", expanded=False):
    if st.button("案件抽出（Notionから）"):
        try:
            write_to_google_sheets()
            st.success("スプレッドシートへ書き込み完了")
        except Exception as e:
            st.error(f"エラー発生: {e}")

# 外注費の反映（Notionへの最終更新）
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
            st.success("外注費反映完了")
        except Exception as e:
            st.error(f"エラー発生: {e}")
