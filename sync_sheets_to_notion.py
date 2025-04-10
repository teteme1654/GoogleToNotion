from collections import defaultdict
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from notion_client import Client
from datetime import datetime
import time

GOOGLE_CREDENTIALS_FILE = "notionsyncproject-e26760681b25.json"
SPREADSHEET_ID = "1a6fFq4ZNUd5YYqdrNsHnhXaWxeiptbE3dLWdZK_NuTg"
SHEET_NAME = "4月2025"

NOTION_API_KEY = "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"
NOTION_DATABASE_ID = "1b762f86d9b080df84f6e623b6e8a5a0"

notion = Client(auth=NOTION_API_KEY)

update_log = []
sync_log = []

請求月 = "4"

def format_date(date_str):
    if not date_str or date_str.strip() == "":
        return None
    try:
        current_year = datetime.now().year
        return datetime.strptime(f"{current_year}/{date_str}", "%Y/%m/%d")
    except ValueError as e:
        print(f"[エラー] 日付変換失敗: {date_str} → {e}")
        return None

def get_existing_notion_entries():
    existing_entries = defaultdict(list)
    response = notion.databases.query(database_id=NOTION_DATABASE_ID)

    for page in response["results"]:
        page_id = page["id"]
        properties = page["properties"]

        project_name = properties["プロジェクト名"]["title"][0]["text"]["content"].strip() if properties["プロジェクト名"]["title"] else ""
        client_name = properties["クライアント名"]["select"]["name"].strip() if properties["クライアント名"].get("select") else ""

        start_date = properties["案件期間"]["date"]["start"] if properties["案件期間"]["date"] else None
        end_date = properties["案件期間"]["date"].get("end") or start_date

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

def add_heading_block(parent_page_id, text):
    try:
        notion.blocks.children.append(
            block_id=parent_page_id,
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": text}}]
                    }
                }
            ]
        )
        print(f"[追加] 見出し「{text}」を追加しました")
    except Exception as e:
        print(f"[エラー] 見出し追加失敗（{text}）: {e}")

def add_paragraph_block(parent_page_id, text):
    try:
        notion.blocks.children.append(
            block_id=parent_page_id,
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": text}}]
                    }
                }
            ]
        )
        print(f"[追加] 段落「{text}」を追加しました")
    except Exception as e:
        print(f"[エラー] 段落追加失敗（{text}）: {e}")

def add_child_page_using_create(parent_page_id, title):
    try:
        child_page = notion.pages.create(
            parent={"page_id": parent_page_id},
            properties={
                "title": [{"type": "text", "text": {"content": title}}]
            }
        )
        print(f"[追加] 子ページ（create）「{title}」を追加しました")
    except Exception as e:
        print(f"[エラー] 子ページ作成失敗（{title}）: {e}")

def add_invoice_blocks(parent_page_id):
    add_heading_block(parent_page_id, "このプロジェクトについて")
    time.sleep(0.5)
    add_paragraph_block(parent_page_id, "\n\n")
    time.sleep(0.5)
    add_child_page_using_create(parent_page_id, "請求関連")
    time.sleep(0.5)
    add_paragraph_block(parent_page_id, "\n\n")
    time.sleep(0.5)
    add_child_page_using_create(parent_page_id, "技術仕様")

def add_or_update_notion(client_name, project_name, location, vehicle, start_date, end_date, existing_entries):
    formatted_start_date = format_date(start_date)
    formatted_end_date = format_date(end_date) if end_date else formatted_start_date

    if formatted_start_date is None or formatted_end_date is None:
        print(f"[エラー] 日付がNoneです: {project_name} ({client_name}) → start: {formatted_start_date}, end: {formatted_end_date}")
        return

    if formatted_start_date > formatted_end_date:
        formatted_start_date, formatted_end_date = formatted_end_date, formatted_start_date

    project_name = project_name.strip()
    client_name = client_name.strip()
    entry_key = (project_name, client_name)

    print(f"[送信チェック] {entry_key}, {formatted_start_date} → {formatted_end_date}")

    if entry_key in existing_entries:
        for entry in existing_entries[entry_key]:
            old_start_date = entry["start_date"]
            old_end_date = entry["end_date"]

            if old_start_date == formatted_start_date and old_end_date == formatted_end_date:
                print(f"[スキップ] 既存データ {project_name} ({client_name}) {formatted_start_date} → {formatted_end_date}")
                return

            print(f"[更新] {project_name} ({client_name}) {formatted_start_date} → {formatted_end_date}")
            try:
                notion.pages.update(
                    page_id=entry["page_id"],
                    properties={
                        "案件期間": {"date": {"start": formatted_start_date.strftime("%Y-%m-%d"), "end": formatted_end_date.strftime("%Y-%m-%d")}},
                        "クライアント名": {"select": {"name": client_name}},
                        "場所": {"rich_text": [{"type": "text", "text": {"content": location or ""}}]},
                        "車両": {"rich_text": [{"type": "text", "text": {"content": vehicle or ""}}]},
                        "タグ": {"multi_select": [{"name": "案件"}]},
                        "請求月": {"select": {"name": 請求月}},
                    }
                )
                update_log.append(entry_key)
                print(f"[更新成功] {project_name} ({client_name}) {formatted_start_date}")
            except Exception as e:
                print(f"[エラー] Notion 更新失敗: {e}")
        return

    print(f"[新規登録] {project_name} ({client_name}) {formatted_start_date}")
    try:
        response = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "プロジェクト名": {"title": [{"type": "text", "text": {"content": project_name}}]},
                "クライアント名": {"select": {"name": client_name}},
                "案件期間": {"date": {"start": formatted_start_date.strftime("%Y-%m-%d"), "end": formatted_end_date.strftime("%Y-%m-%d")}},
                "場所": {"rich_text": [{"type": "text", "text": {"content": location or ""}}]},
                "車両": {"rich_text": [{"type": "text", "text": {"content": vehicle or ""}}]},
                "タグ": {"multi_select": [{"name": "案件"}]},
                "請求月": {"select": {"name": 請求月}},
            }
        )
        new_page_id = response["id"]
        add_invoice_blocks(new_page_id)
        sync_log.append(entry_key)
        print(f"[登録成功] {project_name} ({client_name}) {formatted_start_date}")

        existing_entries[entry_key].append({
            "page_id": response["id"],
            "start_date": formatted_start_date,
            "end_date": formatted_end_date,
        })

    except Exception as e:
        print(f"[エラー] Notion 登録失敗: {e}")

def sync_sheets_to_notion():
    existing_entries = get_existing_notion_entries()
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)
    data = worksheet.get_all_values()

    project_entries = defaultdict(lambda: {"dates": [], "location": "", "vehicle": ""})

    row_idx = 3
    while row_idx < len(data):
        date_raw = data[row_idx][0]
        parsed_date = format_date(date_raw)
        if parsed_date is None:
            row_idx += 4
            continue

        formatted_date = parsed_date.strftime("%m/%d")

        for col_idx in range(4, len(data[row_idx]), 2):
            if row_idx + 3 < len(data):
                client_name = data[row_idx][col_idx].strip() if col_idx < len(data[row_idx]) else ""
                project_name = data[row_idx + 1][col_idx].strip() if col_idx < len(data[row_idx + 1]) else ""
                location = data[row_idx + 2][col_idx].strip() if col_idx < len(data[row_idx + 2]) else ""
                vehicle = data[row_idx + 3][col_idx + 1].strip() if col_idx + 1 < len(data[row_idx + 3]) else ""

                if project_name:
                    entry_key = (project_name, client_name)
                    project_entries[entry_key]["dates"].append(formatted_date)
                    project_entries[entry_key].update({
                        "location": location,
                        "vehicle": vehicle
                    })

        row_idx += 4

    print("==== 読み取ったエントリ ====")
    for key, val in project_entries.items():
        print(key, val)

    for (project_name, client_name), details in project_entries.items():
        start_date = min(details["dates"], key=lambda d: datetime.strptime(d, "%m/%d")) if details["dates"] else None
        end_date = max(details["dates"], key=lambda d: datetime.strptime(d, "%m/%d")) if details["dates"] else None

        if start_date is None or end_date is None:
            continue

        add_or_update_notion(
            client_name=client_name,
            project_name=project_name,
            location=details["location"],
            vehicle=details["vehicle"],
            start_date=start_date,
            end_date=end_date,
            existing_entries=existing_entries
        )

    print("[完了] Notionとの同期が完了しました！")
    print(f"[更新済み] {update_log}")
    print(f"[新規追加] {sync_log}")

sync_sheets_to_notion()
