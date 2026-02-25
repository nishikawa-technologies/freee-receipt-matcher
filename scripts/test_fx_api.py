"""
Frankfurter.app API のテスト
"""

from datetime import datetime
from src.clients.fx_rate_client import FXRateClient

# クライアント初期化
fx_client = FXRateClient(cache_dir="./cache")

# テスト: 2026-02-13 の USD/JPY レート取得
test_date = datetime.strptime("2026-02-13", "%Y-%m-%d").date()

print(f"Testing Frankfurter.app API")
print(f"Fetching USD/JPY rate for {test_date}")
print()

rate = fx_client.get_rate("USD", "JPY", test_date)

if rate:
    print(f"✅ Success!")
    print(f"1 USD = {rate} JPY")
    print()

    # 実際の変換テスト
    usd_amount = 10.0
    jpy_amount = usd_amount * rate
    print(f"Example: ${usd_amount} USD = ¥{jpy_amount:,.2f} JPY")
else:
    print("❌ Failed to fetch rate")
