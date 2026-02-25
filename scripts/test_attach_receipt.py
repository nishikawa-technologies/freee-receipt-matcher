"""
freee 領収書添付APIのテスト
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
receipt_id = 420817636  # アップロード済み領収書ID

base_url = "https://api.freee.co.jp/api/1"
url = f"{base_url}/deals/{deal_id}"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

# まず、現在の deal の状態を取得
print(f"=== Getting current deal {deal_id} ===")
response = requests.get(url, headers=headers, params={"company_id": company_id})
print(f"Status: {response.status_code}")

if response.status_code == 200:
    deal = response.json()["deal"]
    print(f"Current receipts: {deal.get('receipts', [])}")
    print()

    # receipt_ids を追加して PUT
    print(f"=== Attaching receipt {receipt_id} ===")

    payload = {
        "company_id": company_id,
        "receipt_ids": [receipt_id],
    }

    print(f"Payload: {json.dumps(payload, indent=2)}")

    response = requests.put(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
else:
    print(f"Error: {response.text}")
