"""
freee /deals API のレスポンスを確認するテストスクリプト
"""

import json
import yaml
import requests
from datetime import datetime, timedelta

# credentials 読み込み
with open("credentials/freee.yaml") as f:
    creds = yaml.safe_load(f)

access_token = creds["access_token"]
company_id = creds["company_id"]

# API呼び出し
url = "https://api.freee.co.jp/api/1/deals"

# 過去30日間の取引を取得
date_to = datetime.now().date()
date_from = date_to - timedelta(days=30)

params = {
    "company_id": company_id,
    "start_issue_date": date_from.strftime("%Y-%m-%d"),
    "end_issue_date": date_to.strftime("%Y-%m-%d"),
    "limit": 20,  # 最新20件
}

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

print(f"=== freee /deals API Test ===")
print(f"company_id: {company_id}")
print(f"date_range: {date_from} to {date_to}")
print(f"\nCalling API...")

response = requests.get(url, params=params, headers=headers)

print(f"Status: {response.status_code}")
print(f"\n=== Full Response ===")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

# 各dealの主要フィールドをサマリー表示
if response.status_code == 200:
    data = response.json()
    deals = data.get("deals", [])

    print(f"\n=== Summary ({len(deals)} deals) ===")
    for i, deal in enumerate(deals, 1):
        print(f"\nDeal {i}:")
        print(f"  id: {deal.get('id')}")
        print(f"  issue_date: {deal.get('issue_date')}")
        print(f"  amount: {deal.get('amount')}")
        print(f"  status: {deal.get('status')}")
        print(f"  partner_name: {deal.get('partner_name')}")
        print(f"  type: {deal.get('type')}")

        # receiptsフィールドの確認
        receipts = deal.get('receipts', [])
        if receipts:
            print(f"  receipts: {len(receipts)} attached")
        else:
            print(f"  receipts: None")
