#!/usr/bin/env python3
"""
請求履歴ページのテスト - Cookie認証のみ
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clients.connectors.openai_scraper import OpenAIScraper

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

COOKIE_FILE = "credentials/openai_cookies.json"


def main():
    if not Path(COOKIE_FILE).exists():
        print("=" * 80)
        print("Cookie ファイルが見つかりません")
        print("=" * 80)
        print()
        print("まず Cookie をセットアップしてください:")
        print(f"  uv run python scripts/setup_openai_cookies.py")
        print()
        return 1

    print("=" * 80)
    print("OpenAI 請求履歴テスト (Cookie認証)")
    print("=" * 80)
    print()

    scraper = OpenAIScraper(
        cookie_file=COOKIE_FILE,
        headless=True,
        use_google_auth=False,  # Cookie のみ使用
    )

    try:
        # 過去30日分の請求書取得
        invoices = scraper.fetch_invoices(days=30)

        print()
        print("=" * 80)
        print(f"取得成功: {len(invoices)} 件の請求書")
        print("=" * 80)
        print()

        for i, inv in enumerate(invoices, 1):
            print(f"{i:2d}. {inv.date.strftime('%Y-%m-%d')} - ${inv.amount:7.2f} ({inv.currency})")
            print(f"    Invoice ID: {inv.invoice_id}")
            if inv.pdf_url:
                print(f"    PDF URL: {inv.pdf_url[:80]}...")
            print()

        return 0

    except Exception as e:
        logging.error(f"エラー: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
