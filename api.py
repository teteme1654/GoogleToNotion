from flask import Flask, jsonify
from outsource_calculation import update_notion_outsource_cost  # 外注費更新関数をインポート

app = Flask(__name__)

@app.route("/update_notion_outsource_cost", methods=["POST"])
def update_notion():
    """
    Google Sheets のデータを元に Notion の外注費を更新する API
    """
    try:
        update_notion_outsource_cost()
        return jsonify({"message": "Notion の外注費更新が完了しました！"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)


