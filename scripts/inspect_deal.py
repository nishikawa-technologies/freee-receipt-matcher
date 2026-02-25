#!/usr/bin/env python3
"""
実際のdealデータを詳細に確認
"""

import yaml
import requests
import json

# credentials 読み込み
with open("credentials/freee.yaml") as f:
    creds = yaml.safe_load(f)

access_token = creds["access_token"]
company_id = creds["company_id"]

# 最近添付した取引を確認
deal_id = 3284893909  # GO領収書を添付した取引

base_url = "https://api.freee.co.jp/api/1"
url = f"{base_url}/deals/{deal_id}"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

params = {"company_id": company_id}

response = requests.get(url, headers=headers, params=params)
deal_data = response.json()["deal"]

print("=" * 80)
print("FULL DEAL DATA")
print("=" * 80)
print(json.dumps(deal_data, indent=2, ensure_ascii=False))
print()

print("=" * 80)
print("TOP-LEVEL FIELDS")
print("=" * 80)
for key in sorted(deal_data.keys()):
    if key not in ["details", "payments", "receipts"]:
        value = deal_data[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            print(f"{key}: {value}")
        else:
            print(f"{key}: {type(value).__name__}")
print()

print("=" * 80)
print("DETAILS STRUCTURE (first item)")
print("=" * 80)
if deal_data.get("details"):
    print(json.dumps(deal_data["details"][0], indent=2, ensure_ascii=False))
print()

print("=" * 80)
print("PAYMENTS STRUCTURE (first item)")
print("=" * 80)
if deal_data.get("payments"):
    print(json.dumps(deal_data["payments"][0], indent=2, ensure_ascii=False))
