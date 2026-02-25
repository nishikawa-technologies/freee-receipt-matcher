#!/usr/bin/env python3
"""
添付前後でデータが保持されているか確認
"""

import yaml
import requests
import json

# credentials 読み込み
with open("credentials/freee.yaml") as f:
    creds = yaml.safe_load(f)

access_token = creds["access_token"]
company_id = creds["company_id"]

base_url = "https://api.freee.co.jp/api/1"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

# 複数の取引を比較
# 1. 領収書添付済みの取引
deal_ids_with_receipt = [3284893909, 3272516263, 3254694669]

# 2. 領収書未添付の取引
deal_ids_without_receipt = [3295411782, 3280614252]

print("=" * 80)
print("領収書添付済み取引の詳細")
print("=" * 80)

for deal_id in deal_ids_with_receipt:
    url = f"{base_url}/deals/{deal_id}"
    params = {"company_id": company_id}
    response = requests.get(url, headers=headers, params=params)
    deal = response.json()["deal"]

    print(f"\nDeal ID: {deal_id}")
    print(f"  取引先ID (partner_id): {deal.get('partner_id')}")
    print(f"  取引先コード (partner_code): {deal.get('partner_code')}")
    print(f"  参照番号 (ref_number): {deal.get('ref_number')}")
    print(f"  領収書数: {len(deal.get('receipts', []))}")

    if deal.get("details"):
        detail = deal["details"][0]
        print(f"  Details[0]:")
        print(f"    - tax_code (税区分): {detail.get('tax_code')}")
        print(f"    - account_item_id (勘定科目): {detail.get('account_item_id')}")
        print(f"    - item_id (品目): {detail.get('item_id')}")
        print(f"    - vat (消費税): {detail.get('vat')}")
        print(f"    - section_id (部門): {detail.get('section_id')}")

    if deal.get("payments"):
        payment = deal["payments"][0]
        print(f"  Payments[0]:")
        print(f"    - from_walletable_type: {payment.get('from_walletable_type')}")
        print(f"    - from_walletable_id: {payment.get('from_walletable_id')}")
        print(f"    - amount: {payment.get('amount')}")

print("\n" + "=" * 80)
print("領収書未添付取引の詳細（比較用）")
print("=" * 80)

for deal_id in deal_ids_without_receipt:
    url = f"{base_url}/deals/{deal_id}"
    params = {"company_id": company_id}
    response = requests.get(url, headers=headers, params=params)
    deal = response.json()["deal"]

    print(f"\nDeal ID: {deal_id}")
    print(f"  取引先ID (partner_id): {deal.get('partner_id')}")
    print(f"  取引先コード (partner_code): {deal.get('partner_code')}")
    print(f"  参照番号 (ref_number): {deal.get('ref_number')}")
    print(f"  領収書数: {len(deal.get('receipts', []))}")

    if deal.get("details"):
        detail = deal["details"][0]
        print(f"  Details[0]:")
        print(f"    - tax_code (税区分): {detail.get('tax_code')}")
        print(f"    - account_item_id (勘定科目): {detail.get('account_item_id')}")
        print(f"    - item_id (品目): {detail.get('item_id')}")
        print(f"    - vat (消費税): {detail.get('vat')}")
        print(f"    - section_id (部門): {detail.get('section_id')}")

    if deal.get("payments"):
        payment = deal["payments"][0]
        print(f"  Payments[0]:")
        print(f"    - from_walletable_type: {payment.get('from_walletable_type')}")
        print(f"    - from_walletable_id: {payment.get('from_walletable_id')}")
        print(f"    - amount: {payment.get('amount')}")

print("\n" + "=" * 80)
print("結論")
print("=" * 80)
print("領収書添付後も、tax_code, account_item_id, item_id, vat などの")
print("重要フィールドが保持されていることを確認してください。")
print("もし消失している場合は、attach_receipt_to_transaction のコードを")
print("修正する必要があります。")
