"""
freee 領収書添付APIのテスト（詳細版）
"""

import yaml
import requests
import json

# credentials 読み込み
with open("credentials/freee.yaml") as f:
    creds = yaml.safe_load(f)

access_token = creds["access_token"]
company_id = creds["company_id"]

# テスト用
deal_id = 3306574092  # Slack の取引
receipt_id = 420819282  # 最新のアップロード済み領収書ID

base_url = "https://api.freee.co.jp/api/1"
url = f"{base_url}/deals/{deal_id}"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

# 1. 現在の deal を取得
print(f"=== Getting current deal {deal_id} ===")
response = requests.get(url, headers=headers, params={"company_id": company_id})
print(f"Status: {response.status_code}\n")

if response.status_code != 200:
    print(f"Error: {response.text}")
    exit(1)

deal_data = response.json()["deal"]
print(f"Deal type: {deal_data['type']}")
print(f"Issue date: {deal_data['issue_date']}")
print(f"Details: {len(deal_data['details'])} items")
print(f"Current receipts: {[r['id'] for r in deal_data.get('receipts', [])]}")
print()

# 2. receipt_ids を追加して PUT
print(f"=== Attaching receipt {receipt_id} ===")

existing_receipt_ids = [r["id"] for r in deal_data.get("receipts", [])]
receipt_ids = existing_receipt_ids + [receipt_id]

payload = {
    "company_id": company_id,
    "issue_date": deal_data["issue_date"],
    "type": deal_data["type"],
    "details": deal_data["details"],
    "receipt_ids": receipt_ids,
}

print(f"Payload keys: {list(payload.keys())}")
print(f"Receipt IDs: {receipt_ids}\n")

response = requests.put(url, headers=headers, json=payload)
print(f"Status: {response.status_code}")
print(f"Response:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
