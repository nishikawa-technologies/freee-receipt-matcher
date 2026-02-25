"""
freee deal の details 構造を確認
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

print("=== Deal Details ===")
print(json.dumps(deal_data["details"], indent=2, ensure_ascii=False))
print()

# nullを除外したdetailsを作成
def clean_detail(detail):
    """null値を除外"""
    return {k: v for k, v in detail.items() if v is not None}

cleaned_details = [clean_detail(d) for d in deal_data["details"]]

print("=== Cleaned Details ===")
print(json.dumps(cleaned_details, indent=2, ensure_ascii=False))
