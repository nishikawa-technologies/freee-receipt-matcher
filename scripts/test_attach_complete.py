"""
完全なフィールドを含めて領収書添付テスト
"""

import yaml
import requests
import json

# credentials 読み込み
with open("credentials/freee.yaml") as f:
    creds = yaml.safe_load(f)

access_token = creds["access_token"]
company_id = creds["company_id"]

# 既に領収書が添付されている deal を使う
deal_id = 3306574092

base_url = "https://api.freee.co.jp/api/1"
url = f"{base_url}/deals/{deal_id}"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

params = {"company_id": company_id}

# 1. 現在の状態を取得
print("=== Before ===")
response = requests.get(url, headers=headers, params=params)
deal_before = response.json()["deal"]
print(f"Partner ID: {deal_before.get('partner_id')}")
print(f"Payments: {len(deal_before.get('payments', []))} items")
print(f"Receipts: {len(deal_before.get('receipts', []))} items")
print()

# 2. 新しいコードのロジックをシミュレート
def clean_object(obj):
    """null値を除外"""
    if isinstance(obj, dict):
        return {k: clean_object(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [clean_object(item) for item in obj]
    else:
        return obj

cleaned_details = [clean_object(d) for d in deal_before["details"]]
cleaned_payments = [clean_object(p) for p in deal_before.get("payments", [])]

payload = {
    "company_id": company_id,
    "issue_date": deal_before["issue_date"],
    "type": deal_before["type"],
    "details": cleaned_details,
    "payments": cleaned_payments,
    "receipt_ids": [r["id"] for r in deal_before.get("receipts", [])],  # 既存の receipt_ids
}

if deal_before.get("partner_id"):
    payload["partner_id"] = deal_before["partner_id"]
if deal_before.get("partner_code"):
    payload["partner_code"] = deal_before["partner_code"]
if deal_before.get("ref_number") is not None:
    payload["ref_number"] = deal_before["ref_number"]

print("=== Payload ===")
print(f"Keys: {list(payload.keys())}")
print(f"Partner ID in payload: {payload.get('partner_id')}")
print(f"Payments in payload: {len(payload.get('payments', []))}")
print()

# 3. PUT実行
print("=== Executing PUT ===")
response = requests.put(url, headers=headers, json=payload)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    print("✓ Success")

    # 4. 更新後の状態を確認
    print("\n=== After ===")
    response = requests.get(url, headers=headers, params=params)
    deal_after = response.json()["deal"]
    print(f"Partner ID: {deal_after.get('partner_id')}")
    print(f"Payments: {len(deal_after.get('payments', []))} items")
    print(f"Receipts: {len(deal_after.get('receipts', []))} items")

    # 比較
    print("\n=== Verification ===")
    if deal_before.get("partner_id") == deal_after.get("partner_id"):
        print("✓ Partner ID preserved")
    else:
        print("✗ Partner ID changed!")

    if len(deal_before.get("payments", [])) == len(deal_after.get("payments", [])):
        print("✓ Payments preserved")
    else:
        print("✗ Payments changed!")
else:
    print(f"✗ Failed: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
