#!/usr/bin/env python3
"""
重複登録を確認
"""

import yaml
import requests
import json
from collections import defaultdict

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

# 最近添付した取引を確認
deal_ids = [3295411782, 3285487775, 3284893909, 3280614252, 3272516263]

print("=" * 80)
print("領収書の重複確認")
print("=" * 80)

for deal_id in deal_ids:
    url = f"{base_url}/deals/{deal_id}"
    params = {"company_id": company_id}
    response = requests.get(url, headers=headers, params=params)
    deal = response.json()["deal"]

    print(f"\nDeal ID: {deal_id} (金額: ¥{deal['amount']:,}, 日付: {deal['issue_date']})")
    print(f"  領収書数: {len(deal.get('receipts', []))}")

    for i, receipt in enumerate(deal.get("receipts", [])):
        print(f"  [{i+1}] Receipt ID: {receipt['id']}")
        print(f"      発行日: {receipt.get('issue_date')}")
        print(f"      作成日時: {receipt.get('created_at')}")
        print(f"      説明: {receipt.get('description')}")
        print(f"      起源: {receipt.get('origin')}")

        if receipt.get("receipt_metadatum"):
            meta = receipt["receipt_metadatum"]
            print(f"      メタ - 取引先: {meta.get('partner_name')}")
            print(f"      メタ - 日付: {meta.get('issue_date')}")
            print(f"      メタ - 金額: {meta.get('amount')}")

# 全領収書をリストアップして重複チェック
print("\n" + "=" * 80)
print("全領収書のリストアップ")
print("=" * 80)

url = f"{base_url}/receipts"
params = {
    "company_id": company_id,
}
response = requests.get(url, headers=headers, params=params)
receipts = response.json().get("receipts", [])

print(f"\n合計領収書数: {len(receipts)}")

# 同じファイル名や同じ日付・金額の領収書をグループ化
by_metadata = defaultdict(list)
for receipt in receipts:
    if receipt.get("receipt_metadatum"):
        meta = receipt["receipt_metadatum"]
        key = (meta.get("partner_name"), meta.get("issue_date"), meta.get("amount"))
        by_metadata[key].append(receipt["id"])

print("\n重複の可能性がある領収書（同じ取引先・日付・金額）:")
for key, receipt_ids in by_metadata.items():
    if len(receipt_ids) > 1:
        partner, date, amount = key
        print(f"\n  {partner} / {date} / ¥{amount}")
        print(f"    Receipt IDs: {receipt_ids}")
        print(f"    重複数: {len(receipt_ids)}件")
