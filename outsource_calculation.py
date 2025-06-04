import gspread
import unicodedata
from oauth2client.service_account import ServiceAccountCredentials
from notion_client import Client
from datetime import datetime

# ✅ 認証情報
GOOGLE_CREDENTIALS_FILE = "/Users/keisuke/Documents/GitHub/GoogleToNotion/credentials/notionsyncproject-e26760681b25.json"
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
        if start_date and end_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y/%m/%d")
            end_date = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y/%m/%d")
            days = (datetime.strptime(end_date, "%Y/%m/%d") - datetime.strptime(start_date, "%Y/%m/%d")).days + 1
        else:
            start_date = ""
            end_date = ""
            days = 0

        for staff in staff_relations:
            staff_id = staff.get("id", "")
            staff_name = id_to_name_map.get(staff_id, "不明")
            rate_info = outsource_rates.get(staff_id, {"rate": 0, "tax": "税別"})
            standard_rate = rate_info["rate"]
            tax_type = rate_info["tax"]

            project_entries.append([
                project_name, staff_name, tax_type, start_date, end_date, days, standard_rate, "", "0", "0", ""
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

    headers = [
        "プロジェクト名", "外注スタッフ", "税", "開始日", "終了日", "日数", 
        "1日単価（標準）", "1日単価（修正）", "移動日数", "機材チェック日数", "料金"
    ]
    
    sheet.update(range_name="B4:L4", values=[headers])

    project_entries = fetch_notion_data()

    start_row = 5
    if project_entries:
        cleaned_entries = [entry[:11] for entry in project_entries]
        sheet.update(range_name=f"B{start_row}:L{start_row + len(cleaned_entries) - 1}", values=cleaned_entries)

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

        # ✅ Google Sheets のヘッダーをセル位置で明示的に指定
        expected_headers = {
            "プロジェクト名": "B4", 
            "外注スタッフ": "C4", 
            "税": "D4", 
            "開始日": "E4", 
            "終了日": "F4", 
            "日数": "G4",
            "1日単価（標準）": "H4", 
            "1日単価（修正）": "I4", 
            "移動日数": "J4", 
            "機材チェック日数": "K4", 
            "料金": "L4"
        }

        # ✅ スプレッドシートからデータ取得（5行目以降のデータ）
        raw_data = sheet.get_values("B5:L")  # B5 から L列の最終行まで取得

        # ✅ データの辞書化
        data = []
        for row in raw_data:
            if len(row) < len(expected_headers):  # データが不足している場合、空文字で埋める
                row.extend([""] * (len(expected_headers) - len(row)))

            row_dict = {header: row[idx] for idx, header in enumerate(expected_headers.keys())}
            data.append(row_dict)

        print("📜 取得データ:", repr(data[:3]))  # 最初の3行を確認

        project_costs = {}

        for row in data:
            project_name = row.get("プロジェクト名", "").strip()
            cost = row.get("料金", "0").strip()
            cost = int(cost) if cost.isdigit() else 0  # 数値変換

            if project_name:
                project_costs[project_name] = project_costs.get(project_name, 0) + cost

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
