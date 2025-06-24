import json

# ファイルパスを正しく指定
with open("credentials.json") as f:
    data = json.load(f)

# 1行のJSON文字列として出力
print(json.dumps(data))
