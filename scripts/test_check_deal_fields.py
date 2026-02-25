"""
freee deal の全フィールドを確認
"""

import yaml
import requests
import json

# credentials 読み込み
with open("credentials/freee.yaml") as f:
    creds = yaml.safe_load(f)

access_token = creds["access_token"]
company_id = creds["company_id"]

deal_id = 3306574092

base_url = "https://api.freee.co.jp/api/1"
url = f"{base_url}/deals/{deal_id}"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

response = requests.get(url, headers=headers, params={"company_id": company_id})
deal_data = response.json()["deal"]

print("=== Full Deal Data ===")
print(json.dumps(deal_data, indent=2, ensure_ascii=False))
print()

print("=== Top-level Fields ===")
for key in deal_data.keys():
    if key != "details" and key != "payments" and key != "receipts":
        print(f"{key}: {deal_data[key]}")
