import gspread
import unicodedata
from oauth2client.service_account import ServiceAccountCredentials
from notion_client import Client
from datetime import datetime
import streamlit as st
import tempfile
import os
from dotenv import load_dotenv

# ✅ 認証情報の取得
if st.secrets:
    NOTION_API_KEY = st.secrets["notion_token"].strip()
    PROJECT_DB_ID = st.secrets["project_db_id"].strip()
    OUTSOURCE_DB_ID = st.secrets["outsource_db_id"].strip()
    GOOGLE_CREDENTIALS_JSON = st.secrets["google_credentials_json"]
    SPREADSHEET_ID = st.secrets["outsource_spreadsheet_id"]
    SHEET_NAME = st.secrets["outsource_sheet_name"]
else:
    load_dotenv()
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    PROJECT_DB_ID = os.getenv("NOTION_PROJECT_DB_ID")
    OUTSOURCE_DB_ID = os.getenv("NOTION_OUTSOURCE_DB_ID")
    GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
    SPREADSHEET_ID = os.getenv("OUTSOURCE_SPREADSHEET_ID")
    SHEET_NAME = os.getenv("OUTSOURCE_SHEET_NAME")

# 一時ファイルとしてGoogle認証情報を保存
with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".json") as temp:
    temp.write(GOOGLE_CREDENTIALS_JSON)
    GOOGLE_CREDENTIALS_FILE = temp.name

def query_all_pages(notion, database_id, **query_kwargs):
    start_cursor = None
    while True:
        params = dict(query_kwargs)
        if start_cursor:
            params["start_cursor"] = start_cursor

        response = notion.databases.query(database_id=database_id, **params)
        for result in response.get("results", []):
            yield result

        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")
        if not start_cursor:
            break

def fetch_notion_data():
    notion = Client(auth=NOTION_API_KEY)
    projects = list(query_all_pages(
        notion,
        PROJECT_DB_ID,
        filter={"property": "進捗", "status": {"equals": "請求済"}}
    ))

    outsource_rates, id_to_name_map = fetch_outsource_rates(notion)

    project_entries = []

    for project in projects:
        project_name = project["properties"]["プロジェクト名"]["title"][0]["text"]["content"]
        start_date = project["properties"]["案件期間"]["date"]["start"]
        end_date = project["properties"]["案件期間"]["date"]["end"]
        staff_relations = project["properties"]["外注スタッフ"]["relation"]

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

def fetch_outsource_rates(notion):
    response_results = list(query_all_pages(notion, OUTSOURCE_DB_ID))

    outsource_rates = {}
    id_to_name_map = {}

    for record in response_results:
        staff_id = record["id"]
        staff_name = record["properties"]["名前"]["title"][0]["text"]["content"]
        tax_property = record["properties"].get("税", {})
        tax_type = tax_property["select"]["name"] if tax_property.get("select") else ""
        rate = record["properties"]["1日単価"]["number"] if "1日単価" in record["properties"] and record["properties"]["1日単価"]["number"] is not None else 0
        outsource_rates[staff_id] = {"rate": rate, "tax": tax_type}
        id_to_name_map[staff_id] = staff_name

    return outsource_rates, id_to_name_map

def write_to_google_sheets(notion_token=NOTION_API_KEY, project_db_id=PROJECT_DB_ID, outsource_db_id=OUTSOURCE_DB_ID, credentials_file=GOOGLE_CREDENTIALS_FILE, outsource_spreadsheet_id=SPREADSHEET_ID, outsource_sheet_name=SHEET_NAME):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(outsource_spreadsheet_id).worksheet(outsource_sheet_name)

    headers = [
        "プロジェクト名", "外注スタッフ", "税", "開始日", "終了日", "日数",
        "1日単価（標準）", "1日単価（修正）", "移動日数", "機材チェック日数", "料金"
    ]

    sheet.update(range_name="B4:L4", values=[headers])

    global NOTION_API_KEY, PROJECT_DB_ID, OUTSOURCE_DB_ID
    NOTION_API_KEY = notion_token
    PROJECT_DB_ID = project_db_id
    OUTSOURCE_DB_ID = outsource_db_id

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

def update_notion_outsource_cost(notion_token=NOTION_API_KEY, project_db_id=PROJECT_DB_ID, outsource_db_id=OUTSOURCE_DB_ID, outsource_spreadsheet_id=SPREADSHEET_ID, outsource_sheet_name=SHEET_NAME):
    try:
        
        notion = Client(auth=notion_token)
        print("🧪 渡された NOTION TOKEN:", repr(notion_token[:10]))

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(outsource_spreadsheet_id).worksheet(outsource_sheet_name)

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

        raw_data = sheet.get_values("B5:L")

        data = []
        for row in raw_data:
            if len(row) < len(expected_headers):
                row.extend([""] * (len(expected_headers) - len(row)))
            row_dict = {header: row[idx] for idx, header in enumerate(expected_headers.keys())}
            data.append(row_dict)

        print("📜 取得データ:", repr(data[:3]))

        project_costs = {}
        for row in data:
            project_name = row.get("プロジェクト名", "").strip()
            cost = row.get("料金", "0").strip()
            cost = int(cost) if cost.isdigit() else 0
            if project_name:
                project_costs[project_name] = project_costs.get(project_name, 0) + cost

        notion_projects = list(query_all_pages(notion, project_db_id))

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
    write_to_google_sheets(
        notion_token=NOTION_API_KEY,
        project_db_id=PROJECT_DB_ID,
        outsource_db_id=OUTSOURCE_DB_ID,
        credentials_file=GOOGLE_CREDENTIALS_FILE,
        outsource_spreadsheet_id=SPREADSHEET_ID,
        outsource_sheet_name=SHEET_NAME
    )
