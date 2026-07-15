"""名寄せモジュール: セレクト型プロパティの表記ゆれを検出・統合する."""

import json

import streamlit as st
from notion_client import Client

from sync_sheets_to_notion import (
    _get_anthropic_client,
    _notion_database_query,
    query_all_notion_pages,
)


def get_existing_select_options(notion, database_id, property_name):
    """Notion DBスキーマ + 既存ページから既存セレクト値を収集."""
    options = set()

    # 1) スキーマから定義済みオプションを取得
    try:
        db_info = notion.databases.retrieve(database_id=database_id)
        prop_schema = db_info.get("properties", {}).get(property_name, {})
        if prop_schema.get("type") == "select":
            for opt in prop_schema.get("select", {}).get("options", []):
                name = opt.get("name", "").strip()
                if name:
                    options.add(name)
    except Exception as e:
        print(f"[警告] スキーマ取得失敗: {e}")

    # 2) 既存ページから実際に使われている値を取得
    for page in query_all_notion_pages(notion, database_id):
        prop = page.get("properties", {}).get(property_name, {})
        select = prop.get("select") or {}
        name = select.get("name", "").strip()
        if name:
            options.add(name)

    return sorted(options)


def find_new_values(incoming_values, existing_options):
    """シートにあってNotionにない値を抽出."""
    existing_set = set(existing_options)
    return sorted(set(v for v in incoming_values if v and v not in existing_set))


def match_names_with_claude(new_values, existing_options, property_name="クライアント名"):
    """Claudeに一括判定させてJSON形式で返す.

    Returns:
        list[dict]: 各要素は {new_value, suggested_match, confidence, reason}
        suggested_matchがNoneの場合はマッチなし（新規追加推奨）
    """
    if not new_values:
        return []

    client = _get_anthropic_client()
    if client is None:
        return None  # API利用不可

    prompt = f"""あなたは日本のビジネスデータの名寄せ専門家です。
以下の「新しい値」が「既存の値」のいずれかと同じエンティティを指しているか判定してください。

## ルール
- 日本のビジネス命名規則に従って判定:
  - 「株式会社」「(株)」「（株）」「㈱」は同一とみなす
  - 「有限会社」「(有)」「（有）」も同様
  - 全角・半角の違いは同一とみなす（例: ＡＢＣ = ABC）
  - スペースの有無・種類の違いは同一とみなす
  - 明らかな略称も考慮（例: 「○○建設」と「○○建」）
- **地名が異なる場合は別エンティティ**として扱う（例: 「ABC東京」と「ABC大阪」は別）
- 不明な場合・自信がない場合は suggested_match を null にする（誤マッチより見逃しが安全）

## プロパティ名
{property_name}

## 既存の値
{json.dumps(existing_options, ensure_ascii=False)}

## 新しい値
{json.dumps(new_values, ensure_ascii=False)}

## 出力形式
以下のJSON配列のみを返してください。説明文は不要です。
```json
[
  {{
    "new_value": "新しい値",
    "suggested_match": "既存の値" or null,
    "confidence": 0.0-1.0,
    "reason": "判定理由（日本語で簡潔に）"
  }}
]
```"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text.strip()

        # JSON部分を抽出（```json ... ``` で囲まれている場合に対応）
        if "```" in response_text:
            json_start = response_text.find("[")
            json_end = response_text.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                response_text = response_text[json_start:json_end]

        results = json.loads(response_text)
        # バリデーション
        validated = []
        for item in results:
            validated.append({
                "new_value": item.get("new_value", ""),
                "suggested_match": item.get("suggested_match"),
                "confidence": float(item.get("confidence", 0)),
                "reason": item.get("reason", ""),
            })
        return validated

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"[警告] Claude応答パース失敗: {e}")
        return None
    except Exception as e:
        print(f"[警告] Claude API呼び出し失敗: {e}")
        return None


def apply_name_mapping(project_entries, mapping):
    """確定したマッピングを project_entries に適用.

    Args:
        project_entries: dict of {(project_name, client_name): {dates, location, vehicle}}
        mapping: dict of {old_client_name: new_client_name}

    Returns:
        dict: マッピング適用後の新しい project_entries
    """
    if not mapping:
        return project_entries

    new_entries = {}
    for (project_name, client_name), val in project_entries.items():
        mapped_name = mapping.get(client_name, client_name)
        new_key = (project_name, mapped_name)
        if new_key in new_entries:
            # 同じキーが既に存在する場合はdatesをマージ
            new_entries[new_key]["dates"].extend(val["dates"])
            if val["location"]:
                new_entries[new_key]["location"] = val["location"]
            if val["vehicle"]:
                new_entries[new_key]["vehicle"] = val["vehicle"]
        else:
            new_entries[new_key] = {
                "dates": list(val["dates"]),
                "location": val["location"],
                "vehicle": val["vehicle"],
            }
    return new_entries
