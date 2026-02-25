#!/usr/bin/env python3
"""
2026-01-09の¥5,700取引の重複を確認
"""

import yaml
import requests
import json
from datetime import datetime

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

# 2026-01-09の取引を検索
url = f"{base_url}/deals"
params = {
    "company_id": company_id,
    "start_issue_date": "2026-01-09",
    "end_issue_date": "2026-01-09",
    "limit": 100,
}

response = requests.get(url, headers=headers, params=params)
deals = response.json().get("deals", [])

print("=" * 80)
print("2026-01-09 の全取引")
print("=" * 80)
print(f"\n合計: {len(deals)}件\n")

# ¥5,700の取引を探す
matching_deals = [d for d in deals if d.get("amount") == 5700]

print(f"¥5,700 の取引: {len(matching_deals)}件\n")

for i, deal in enumerate(matching_deals, 1):
    print("=" * 80)
    print(f"取引 #{i}")
    print("=" * 80)
    print(f"ID: {deal['id']}")
    print(f"金額: ¥{deal['amount']:,}")
    print(f"日付: {deal['issue_date']}")
    print(f"ステータス: {deal['status']}")
    print(f"タイプ: {deal['type']}")
    print(f"取引先ID: {deal.get('partner_id')}")
    print(f"取引先名: {deal.get('partner_name')}")
    print(f"取引の由来: {deal.get('deal_origin_name')}")
    print(f"領収書数: {len(deal.get('receipts', []))}")

    if deal.get("receipts"):
        for j, receipt in enumerate(deal["receipts"], 1):
            print(f"\n  領収書 [{j}]:")
            print(f"    ID: {receipt['id']}")
            print(f"    説明: {receipt.get('description')}")
            print(f"    作成日時: {receipt.get('created_at')}")
            print(f"    起源: {receipt.get('origin')}")

    if deal.get("details"):
        print(f"\n  Details (最初の1件):")
        detail = deal["details"][0]
        print(f"    勘定科目ID: {detail.get('account_item_id')}")
        print(f"    品目ID: {detail.get('item_id')}")
        print(f"    税区分: {detail.get('tax_code')}")
        print(f"    金額: ¥{detail.get('amount'):,}")
        print(f"    消費税: ¥{detail.get('vat')}")

    if deal.get("payments"):
        print(f"\n  Payments (最初の1件):")
        payment = deal["payments"][0]
        print(f"    支払元タイプ: {payment.get('from_walletable_type')}")
        print(f"    支払元ID: {payment.get('from_walletable_id')}")
        print(f"    金額: ¥{payment.get('amount'):,}")
        print(f"    日付: {payment.get('date')}")

    print()

print("=" * 80)
print("分析")
print("=" * 80)
if len(matching_deals) > 1:
    print(f"\n⚠️ 同じ日付・金額の取引が {len(matching_deals)} 件存在します")
    print("\n各取引の違い:")
    for i, deal in enumerate(matching_deals, 1):
        print(f"\n  取引 #{i} (ID: {deal['id']}):")
        print(f"    - 取引の由来: {deal.get('deal_origin_name')}")
        print(f"    - 取引先: {deal.get('partner_name') or '(なし)'}")
        print(f"    - 領収書: {len(deal.get('receipts', []))}件")
        print(f"    - 支払元ID: {deal.get('payments', [{}])[0].get('from_walletable_id') if deal.get('payments') else '(なし)'}")

    print("\n推奨アクション:")
    print("1. どちらか一方の取引を削除する")
    print("2. または、2つの取引が実際に別の支出である可能性を確認する")
else:
    print("\n✓ 重複はありません（1件のみ）")
