import gspread
from oauth2client.service_account import ServiceAccountCredentials
from notion_client import Client
from datetime import datetime

# ✅ 認証情報
GOOGLE_CREDENTIALS_FILE = "notionsyncproject-e26760681b25.json"
SPREADSHEET_ID = "1L5t1VZFF_jYjQP9PDvoF9_3KBXQW_6qTf58qsZ8RJ7A"
SHEET_NAME = "GTN_外注DB計算シート"

NOTION_API_KEY = "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"
PROJECT_DB_ID = "1b762f86d9b080df84f6e623b6e8a5a0"
OUTSOURCE_DB_ID = "0206402d95ff467c9117d05b5f3fe623"

# ✅ Notion API 認証
notion = Client(auth=NOTION_API_KEY)

def fetch_notion_data():
    """
    Notionのデータベースから「請求済」のプロジェクトを取得し、
    外注スタッフ情報を抽出する。
    """
    projects = notion.databases.query(
        database_id=PROJECT_DB_ID,
        filter={"property": "進捗", "status": {"equals": "請求済"}}
    )["results"]

    outsource_rates, id_to_name_map = fetch_outsource_rates()

    project_entries = []
    
    for project in projects:
        project_name = project["properties"]["プロジェクト名"]["title"][0]["text"]["content"]
        start_date = project["properties"]["案件期間"]["date"]["start"]
        end_date = project["properties"]["案件期間"]["date"]["end"]
        staff_relations = project["properties"]["外注スタッフ"]["relation"]

        # **日付を安全に処理（datetime → 文字列）**
        if start_date and end_date:  # 両方の日付がある場合
            start_date = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y/%m/%d")
            end_date = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y/%m/%d")
            days = (datetime.strptime(end_date, "%Y/%m/%d") - datetime.strptime(start_date, "%Y/%m/%d")).days + 1
        else:
            start_date = ""  # 空欄にする
            end_date = ""
            days = 0

        for staff in staff_relations:
            staff_id = staff.get("id", "")

            # 外注スタッフ情報を取得
            staff_name = id_to_name_map.get(staff_id, "不明")
            rate_info = outsource_rates.get(staff_id, {"rate": 0, "tax": "税別"})
            standard_rate = rate_info["rate"]
            tax_type = rate_info["tax"]

            project_entries.append([
                project_name, staff_name, tax_type, start_date, end_date, days, standard_rate, "", "0", "0", ""  # 末尾のカンマ対策
            ])


    return project_entries

def fetch_outsource_rates():
    """ Notionの外注DBからデータを取得する """
    response = notion.databases.query(database_id=OUTSOURCE_DB_ID)
    outsource_rates = {}
    id_to_name_map = {}

    for record in response["results"]:
        staff_id = record["id"]
        staff_name = record["properties"]["名前"]["title"][0]["text"]["content"]
        tax_property = record["properties"].get("税", {})
        tax_type = tax_property["select"]["name"] if tax_property.get("select") else ""
        rate = record["properties"]["1日単価"]["number"] if "1日単価" in record["properties"] and record["properties"]["1日単価"]["number"] is not None else 0
        outsource_rates[staff_id] = {"rate": rate, "tax": tax_type}
        id_to_name_map[staff_id] = staff_name

    return outsource_rates, id_to_name_map

def write_to_google_sheets():
    """
    Notionから取得したデータをGoogle Sheetsに書き込む
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    # ヘッダー情報
    headers = [
        "プロジェクト名", "外注スタッフ", "税", "開始日", "終了日", "日数", 
        "1日単価（標準）", "1日単価（修正）", "移動日数", "機材チェック日数", "料金"
    ]
    
    # ヘッダー書き込み
    sheet.update(range_name="B4:L4", values=[headers])

    # Notionからデータ取得
    project_entries = fetch_notion_data()

    # 余分なデータがないかチェックしつつ書き込む
    start_row = 5
    if project_entries:
        cleaned_entries = [entry[:11] for entry in project_entries]  # L列（11列）までのデータに制限
        sheet.update(range_name=f"B{start_row}:L{start_row + len(cleaned_entries) - 1}", values=cleaned_entries)

    # **料金計算式の修正**
    for i in range(len(project_entries)):
        row_num = start_row + i
        formula = f"=IF(EXACT(D{row_num}, \"税別\"), 1.1, 1) * IF(ISNUMBER(I{row_num}), I{row_num}, H{row_num}) * (G{row_num} - (IF(ISNUMBER(J{row_num}), J{row_num}, 0) * 0.5) - (IF(ISNUMBER(K{row_num}), K{row_num}, 0) * 0.5))"
        sheet.update_acell(f"L{row_num}", formula)

    print("✅ Notion → Google Sheets へのデータ転送が完了しました。")


def update_notion_outsource_cost():
    """Google Sheets から外注費を取得し、Notion のプロジェクト DB に反映する"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        # ✅ Google Sheets のヘッダー行を取得
        actual_headers = sheet.row_values(4)  # 4行目のヘッダーを取得
        actual_headers = [h.strip() for h in actual_headers if h.strip()]  # 空白の要素を削除してトリム
        print("📌 実際のGoogle Sheets ヘッダー:", repr(actual_headers))

        # ✅ 期待するヘッダーを明示
        expected_headers = [
            "プロジェクト名", "外注スタッフ", "税", "開始日", "終了日", "日数",
            "1日単価（標準）", "1日単価（修正）", "移動日数", "機材チェック日数", "料金"
        ]
        print("🔍 期待するヘッダー:", repr(expected_headers))

        # ✅ 並び順を強制的に一致させる
        actual_headers = sorted(actual_headers, key=lambda x: expected_headers.index(x) if x in expected_headers else len(expected_headers))
        print("🛠 並び替え後のヘッダー:", repr(actual_headers))

        # ✅ データ型チェック
        print(f"📏 ヘッダーの長さ: 実際={len(actual_headers)}, 期待={len(expected_headers)}")
        print(f"🛠 データ型: 実際={type(actual_headers)}, 期待={type(expected_headers)}")

        # ✅ Unicodeコードポイントチェック（微妙な文字違いがないか確認）
        for i, (act, exp) in enumerate(zip(actual_headers, expected_headers)):
            print(f"🔠 {i+1}列目 - 実際: {[ord(c) for c in act]}, 期待: {[ord(c) for c in exp]}")

        # ✅ データ取得（expected_headers を指定）
        data = sheet.get_all_records(expected_headers=expected_headers)
        print("📜 取得データ:", repr(data[:3]))  # 最初の3行を確認

        project_costs = {}

        for row in data:
            project_name = row["プロジェクト名"]
            cost = row["料金"]

            if project_name in project_costs:
                project_costs[project_name] += cost
            else:
                project_costs[project_name] = cost

        notion_projects = notion.databases.query(database_id=PROJECT_DB_ID)["results"]

        for project in notion_projects:
            notion_project_name = project["properties"]["プロジェクト名"]["title"][0]["text"]["content"]
            project_id = project["id"]

            if notion_project_name in project_costs:
                notion.pages.update(
                    page_id=project_id,
                    properties={"外注費": {"number": project_costs[notion_project_name]}}
                )
                print(f"✅ {notion_project_name} の外注費を {project_costs[notion_project_name]} に更新しました！")

    except Exception as e:
        print(f"❌ エラー: {e}")


if __name__ == "__main__":
    write_to_google_sheets()
