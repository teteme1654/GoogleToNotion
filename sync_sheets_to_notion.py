from collections import defaultdict
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from notion_client import Client
from datetime import datetime

# Google Sheets API の認証情報
GOOGLE_CREDENTIALS_FILE = "notionsyncproject-e26760681b25.json"  # JSONキーのファイル
SPREADSHEET_ID = "1a6fFq4ZNUd5YYqdrNsHnhXaWxeiptbE3dLWdZK_NuTg"  # スプレッドシートのID
SHEET_NAME = "4月2025"  # シート名

# Notion API の設定
NOTION_API_KEY = "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"  # Notion APIキー
NOTION_DATABASE_ID = "1b762f86d9b080df84f6e623b6e8a5a0"  # Notion データベースID

# Notion API クライアントを作成
notion = Client(auth=NOTION_API_KEY)

# 📌 Googleスプレッドシートの日付を ISO 8601 形式 に変換
def format_date(date_str):
    """ MM/DD の日付を YYYY/MM/DD に変換する関数 """
    if not date_str or date_str.strip() == "":
        return None  

    try:
        current_year = datetime.now().year  
        return datetime.strptime(f"{current_year}/{date_str}", "%Y/%m/%d")
    except ValueError as e:
        print(f"❌ 日付変換エラー: {date_str} → {e}")
        return None

# 📌 Notion の既存データを取得し、辞書に保存（統合処理用）
# Notion の既存データを取得
def get_existing_notion_entries():
    existing_entries = defaultdict(list)
    response = notion.databases.query(database_id=NOTION_DATABASE_ID)

    for page in response["results"]:
        page_id = page["id"]
        properties = page["properties"]

        project_name = properties["プロジェクト名"]["title"][0]["text"]["content"].strip() if properties["プロジェクト名"]["title"] else ""

        # クライアント名が `select` または `rich_text` にあるかチェック
        client_name = ""
        if "select" in properties["クライアント名"]:
            client_name = properties["クライアント名"]["select"]["name"].strip() if properties["クライアント名"]["select"] else ""
        elif "rich_text" in properties["クライアント名"]:
            client_name = properties["クライアント名"]["rich_text"][0]["text"]["content"].strip() if properties["クライアント名"]["rich_text"] else ""

        # 📌 Notionの日時データは "YYYY-MM-DDT00:00:00.000+09:00" の形になっているので、修正
        start_date = properties["案件期間"]["date"]["start"] if properties["案件期間"]["date"] else None
        end_date = properties["案件期間"]["date"]["end"] if properties["案件期間"]["date"] else start_date

        if start_date:
            start_date = datetime.strptime(start_date[:10], "%Y-%m-%d")  # 🔍 `T00:00:00.000+09:00` を切り取る
        if end_date:
            end_date = datetime.strptime(end_date[:10], "%Y-%m-%d")  # 🔍 `T00:00:00.000+09:00` を切り取る

        entry_key = (project_name, client_name)
        existing_entries[entry_key].append({
            "page_id": page_id,
            "start_date": start_date,
            "end_date": end_date
        })

    return existing_entries

# 📌 Notion にデータを追加または更新
def add_or_update_notion(client_name, project_name, location, vehicle, start_date, end_date, existing_entries):
    formatted_start_date = format_date(start_date)
    formatted_end_date = format_date(end_date) if end_date else formatted_start_date

    if formatted_start_date is None or formatted_end_date is None:
        print(f"❌ エラー: {project_name} ({client_name}) の日付が None になっています → start: {formatted_start_date}, end: {formatted_end_date}")
        return

    if formatted_start_date > formatted_end_date:
        formatted_start_date, formatted_end_date = formatted_end_date, formatted_start_date

    project_name = project_name.strip()
    client_name = client_name.strip()
    entry_key = (project_name, client_name)

    print(f"📡 Notion API 送信チェック: {entry_key}, {formatted_start_date} → {formatted_end_date}")

    # ✅ `existing_entries` にデータがあるか確認
    if entry_key in existing_entries:
        for entry in existing_entries[entry_key]:
            old_start_date = entry["start_date"]
            old_end_date = entry["end_date"]

            if old_start_date == formatted_start_date and old_end_date == formatted_end_date:
                print(f"⏩ スキップ: 既存データ {project_name} ({client_name}) {formatted_start_date} → {formatted_end_date}")
                return

            print(f"🔄 Notion 更新: {project_name} ({client_name}) {formatted_start_date} → {formatted_end_date}")
            try:
                notion.pages.update(
                    page_id=entry["page_id"],
                    properties={
                        "案件期間": {"date": {"start": formatted_start_date.strftime("%Y-%m-%d"), "end": formatted_end_date.strftime("%Y-%m-%d")}},
                        "クライアント名": {"select": {"name": client_name}},
                        "場所": {"rich_text": [{"text": {"content": location or ""}}]},
                        "車両": {"rich_text": [{"text": {"content": vehicle or ""}}]},
                        "タグ": {"multi_select": [{"name": "案件"}]},  # ✅ 「案件」タグを付与
                    }
                )
                print(f"✅ Notion 更新成功: {project_name} ({client_name}) {formatted_start_date}")
            except Exception as e:
                print(f"❌ Notion 更新エラー: {e}")
        return

    # 🆕 **新規登録**
    print(f"🆕 Notion 新規登録: {project_name} ({client_name}) {formatted_start_date}")
    try:
        response = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "プロジェクト名": {"title": [{"text": {"content": project_name}}]},
                "クライアント名": {"select": {"name": client_name}},
                "案件期間": {"date": {"start": formatted_start_date.strftime("%Y-%m-%d"), "end": formatted_end_date.strftime("%Y-%m-%d")}},
                "場所": {"rich_text": [{"text": {"content": location or ""}}]},
                "車両": {"rich_text": [{"text": {"content": vehicle or ""}}]},
                "タグ": {"multi_select": [{"name": "案件"}]},  # ✅ 「案件」タグを付与
            }
        )
        print(f"✅ Notion に登録成功: {project_name} ({client_name}) {formatted_start_date}")

        existing_entries[entry_key].append({
            "page_id": response["id"],
            "start_date": formatted_start_date,
            "end_date": formatted_end_date,
        })

    except Exception as e:
        print(f"❌ Notion 登録エラー: {e}")



# 📌 Googleスプレッドシートのデータ取得 & Notionへの送信
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
                project_name = data[row_idx][col_idx].strip() if col_idx < len(data[row_idx]) else ""
                client_name = data[row_idx + 1][col_idx].strip() if col_idx < len(data[row_idx + 1]) else ""
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

    for (client_name, project_name), details in project_entries.items():
        start_date = min(details["dates"], key=lambda d: datetime.strptime(d, "%m/%d")) if details["dates"] else None
        end_date = max(details["dates"], key=lambda d: datetime.strptime(d, "%m/%d")) if details["dates"] else None

        if start_date is None or end_date is None:
            continue  

        add_or_update_notion(client_name, project_name, details["location"], details["vehicle"], start_date, end_date, existing_entries)

    print("✅ Notion との同期が完了しました！")

sync_sheets_to_notion()