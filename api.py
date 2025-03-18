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

# 🔹 スリープ防止用のエンドポイントを追加（何もしない）
@app.route("/healthcheck", methods=["GET"])
def healthcheck():
    """ スリープ防止用エンドポイント（単に200を返すだけ）"""
    return jsonify({"message": "Server is running"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
