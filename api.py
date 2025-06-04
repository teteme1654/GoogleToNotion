from flask import Flask, jsonify
from outsource_calculation import update_notion_outsource_cost, write_to_google_sheets

app = Flask(__name__)

@app.route("/update_notion_outsource_cost", methods=["POST"])
def update_notion():
    try:
        update_notion_outsource_cost()
        return jsonify({"message": "Notion 外注費更新完了！"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/write_to_google_sheets", methods=["POST"])
def write_sheets():
    try:
        write_to_google_sheets()
        return jsonify({"message": "Google Sheets 更新完了！"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/healthcheck", methods=["GET"])
def healthcheck():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(debug=True)
