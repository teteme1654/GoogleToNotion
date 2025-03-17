from notion_client import Client

# Notion API の設定
NOTION_API_KEY = "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"  # Notion APIキー
NOTION_DATABASE_ID = "1ac62f86d9b080c8bf6cdf01e403987a"  # Notion データベースID

# Notion API クライアントを作成
notion = Client(auth=NOTION_API_KEY)

# Notion にデータを追加する関数
def add_to_notion(project_name, client_name, start_date, end_date, remarks, staff):
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "プロジェクト名": {"title": [{"text": {"content": project_name}}]},
            "クライアント名": {"rich_text": [{"text": {"content": client_name}}]},
            "案件期間": {"date": {"start": start_date, "end": end_date}},
            "備考": {"rich_text": [{"text": {"content": remarks}}]},
            "スタッフ": {"rich_text": [{"text": {"content": staff}}]},
        }
    )

# Notion に登録するデータの例
example_data = {
    "プロジェクト名": "映像制作プロジェクト",
    "クライアント名": "ABC株式会社",
    "案件期間": ("2025-02-01", "2025-02-03"),
    "備考": "撮影2日間",
    "スタッフ": "野口, 葛巻"
}

# Notion にデータを送信
add_to_notion(
    example_data["プロジェクト名"],
    example_data["クライアント名"],
    example_data["案件期間"][0],  # 開始日
    example_data["案件期間"][1],  # 終了日
    example_data["備考"],
    example_data["スタッフ"]
)

print("✅ Notion にデータを送信しました！")
