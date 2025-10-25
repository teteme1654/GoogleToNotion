from collections import defaultdict
import gspread
from google.oauth2.service_account import Credentials
from notion_client import Client
from datetime import datetime
import time
import streamlit as st
import tempfile
import json

update_log = []
sync_log = []

def format_date(date_str):
    if not date_str or date_str.strip() == "":
        return None
    try:
        current_year = datetime.now().year
        return datetime.strptime(f"{current_year}/{date_str}", "%Y/%m/%d")
    except ValueError as e:
        print(f"[エラー] 日付変換失敗: {date_str} → {e}")
        return None

def get_existing_notion_entries(notion, NOTION_DATABASE_ID):
    existing_entries = defaultdict(list)
    response = notion.databases.query(database_id=NOTION_DATABASE_ID)
    for page in response["results"]:
        page_id = page["id"]
        properties = page.get("properties", {})

        title_raw = properties.get("プロジェクト名", {}).get("title", [])
        if title_raw and isinstance(title_raw[0], dict):
            project_name = title_raw[0].get("text", {}).get("content", "").strip()
        else:
            project_name = ""

        client_raw = properties.get("クライアント名") or {}
        client_select = client_raw.get("select") or {}
        client_name = client_select.get("name", "").strip()

        period_raw = properties.get("案件期間") or {}
        date_raw = period_raw.get("date") or {}
        start_date = date_raw.get("start")
        end_date = date_raw.get("end") or start_date

        if start_date:
            start_date = datetime.strptime(start_date[:10], "%Y-%m-%d")
        if end_date:
            end_date = datetime.strptime(end_date[:10], "%Y-%m-%d")

        entry_key = (project_name, client_name)
        existing_entries[entry_key].append({
            "page_id": page_id,
            "start_date": start_date,
            "end_date": end_date
        })
    return existing_entries


# 以下 unchanged

def add_heading_block(notion, parent_page_id, text):
    try:
        notion.blocks.children.append(
            block_id=parent_page_id,
            children=[{
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                }
            }]
        )
        print(f"[追加] 見出し「{text}」を追加しました")
    except Exception as e:
        print(f"[エラー] 見出し追加失敗（{text}）: {e}")

def add_paragraph_block(notion, parent_page_id, text):
    try:
        notion.blocks.children.append(
            block_id=parent_page_id,
            children=[{
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                }
            }]
        )
        print(f"[追加] 段落「{text}」を追加しました")
    except Exception as e:
        print(f"[エラー] 段落追加失敗（{text}）: {e}")

def add_child_page_using_create(notion, parent_page_id, title):
    try:
        notion.pages.create(
            parent={"page_id": parent_page_id},
            properties={"title": [{"type": "text", "text": {"content": title}}]}
        )
        print(f"[追加] 子ページ（create）「{title}」を追加しました")
    except Exception as e:
        print(f"[エラー] 子ページ作成失敗（{title}）: {e}")

def add_invoice_blocks(notion, parent_page_id):
    add_heading_block(notion, parent_page_id, "このプロジェクトについて")
    time.sleep(0.5)
    add_paragraph_block(notion, parent_page_id, "\n\n")
    time.sleep(0.5)
    add_child_page_using_create(notion, parent_page_id, "請求関連")
    time.sleep(0.5)
    add_paragraph_block(notion, parent_page_id, "\n\n")
    time.sleep(0.5)
    add_child_page_using_create(notion, parent_page_id, "技術仕様")

# unchanged 以降は省略なしで編集されているので維持


def add_or_update_notion(notion, NOTION_DATABASE_ID, client_name, project_name, location, vehicle, start_date, end_date, existing_entries):
    formatted_start_date = format_date(start_date)
    formatted_end_date = format_date(end_date) if end_date else formatted_start_date
    if not formatted_start_date or not formatted_end_date:
        print(f"[エラー] 日付がNoneです: {project_name} ({client_name})")
        return
    if formatted_start_date > formatted_end_date:
        formatted_start_date, formatted_end_date = formatted_end_date, formatted_start_date
    entry_key = (project_name.strip(), client_name.strip())
    print(f"[送信チェック] {entry_key}, {formatted_start_date} → {formatted_end_date}")
    props = {
        "案件期間": {"date": {"start": formatted_start_date.strftime("%Y-%m-%d"), "end": formatted_end_date.strftime("%Y-%m-%d")}},
        "クライアント名": {"select": {"name": client_name}},
        "場所": {"rich_text": [{"type": "text", "text": {"content": location or ""}}]},
        "車両": {"rich_text": [{"type": "text", "text": {"content": vehicle or ""}}]},
        "タグ": {"multi_select": [{"name": "案件"}]},
        "請求月": {"select": {"name": str(formatted_start_date.month)}},
        "年度": {"select": {"name": "2025"}}
    }
    if entry_key in existing_entries:
        for entry in existing_entries[entry_key]:
            if entry["start_date"] == formatted_start_date and entry["end_date"] == formatted_end_date:
                print(f"[スキップ] 既存データ {entry_key}")
                return
            try:
                notion.pages.update(page_id=entry["page_id"], properties=props)
                update_log.append(entry_key)
                print(f"[更新成功] {entry_key}")
            except Exception as e:
                print(f"[エラー] Notion 更新失敗: {e}")
        return
    try:
        new_page = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={"プロジェクト名": {"title": [{"type": "text", "text": {"content": project_name}}]}, **props}
        )
        add_invoice_blocks(notion, new_page["id"])
        sync_log.append(entry_key)
        existing_entries[entry_key].append({"page_id": new_page["id"], "start_date": formatted_start_date, "end_date": formatted_end_date})
        print(f"[登録成功] {entry_key}")
    except Exception as e:
        print(f"[エラー] Notion 登録失敗: {e}")

def sync_sheets_to_notion(sheet_name):
    spreadsheet_id = st.secrets["syncsheet_spreadsheet_id"]
    notion_token = st.secrets["notion_token"]
    notion_db_id = st.secrets["project_db_id"]
    credentials_json = st.secrets["google_credentials_json"]

    notion = Client(auth=notion_token)
    existing_entries = get_existing_notion_entries(notion, notion_db_id)

    creds_dict = json.loads(credentials_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)

    data = client.open_by_key(spreadsheet_id).worksheet(sheet_name).get_all_values()
    project_entries = defaultdict(lambda: {"dates": [], "location": "", "vehicle": ""})

    for row_base in range(3, len(data) - 3, 4):
        date_raw = data[row_base][0]
        formatted_date = format_date(date_raw)
        if not formatted_date:
            continue
        date_str = formatted_date.strftime("%m/%d")

        for col in range(4, len(data[row_base]), 2):
            if col + 1 >= len(data[row_base]):
                continue
            project_type_flag = data[row_base][col + 1].strip()
            if not project_type_flag:
                continue

            client_name = data[row_base][col].strip()
            project_name = data[row_base + 1][col].strip()
            location = data[row_base + 2][col].strip()
            vehicle = data[row_base + 3][col + 1].strip() if col + 1 < len(data[row_base + 3]) else ""

            if project_name:
                entry_key = (project_name, client_name)
                project_entries[entry_key]["dates"].append(date_str)
                project_entries[entry_key]["location"] = location
                project_entries[entry_key]["vehicle"] = vehicle

    print("==== 読み取ったエントリ ====")
    for key, val in project_entries.items():
        print(key, val)

    for (project_name, client_name), val in project_entries.items():
        if not val["dates"]:
            continue
        start = min(val["dates"], key=lambda d: datetime.strptime(d, "%m/%d"))
        end = max(val["dates"], key=lambda d: datetime.strptime(d, "%m/%d"))
        add_or_update_notion(notion, notion_db_id, client_name, project_name, val["location"], val["vehicle"], start, end, existing_entries)

    print("[完了] Notionとの同期が完了しました！")
    print(f"[更新済み] {update_log}")
    print(f"[新規追加] {sync_log}")

if __name__ == "__main__":
    DEFAULT_SHEET_NAME = "7月2025"
    sync_sheets_to_notion(DEFAULT_SHEET_NAME)
