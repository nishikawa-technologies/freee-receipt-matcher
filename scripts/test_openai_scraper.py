#!/usr/bin/env python3
"""
OpenAI スクレイパのテストスクリプト

使い方:
    1. 環境変数設定:
       export OPENAI_EMAIL=your@email.com
       export OPENAI_PASSWORD=yourpassword

    2. 実行:
       uv run python scripts/test_openai_scraper.py

    3. または Cookie 認証:
       uv run python scripts/test_openai_scraper.py --use-cookies
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clients.connectors import OpenAIScraper

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="OpenAI 請求書スクレイパテスト")
    parser.add_argument("--days", type=int, default=90, help="取得日数（デフォルト: 90）")
    parser.add_argument("--headless", action="store_true", help="ヘッドレスモード（初回は非推奨）")
    parser.add_argument("--output-dir", default="./temp", help="PDF保存先")
    args = parser.parse_args()

    # Cookie認証ファイル
    cookie_file = "credentials/openai_cookies.json"

    # Cookie存在チェック
    has_cookies = os.path.exists(cookie_file)

    logger.info(f"Cookie file: {cookie_file}")
    logger.info(f"Cookie exists: {has_cookies}")
    logger.info(f"Headless arg: {args.headless}")

    if not has_cookies:
        logger.info("=" * 80)
        logger.info("Cookie が見つかりません")
        logger.info("=" * 80)
        logger.info("")
        logger.info("【推奨】Cookie セットアップスクリプトを使用:")
        logger.info("  uv run python scripts/setup_openai_cookies.py")
        logger.info("")
        logger.info("または、このまま続行してブラウザで認証:")
        logger.info("  1. Chromium ブラウザが開きます")
        logger.info("  2. Google アカウントでログイン")
        logger.info("  3. ログイン完了したらターミナルで Enter キーを押してください")
        logger.info("=" * 80)

        choice = input("\n続行しますか? (y/N): ")
        if choice.lower() != 'y':
            logger.info("中断しました。setup_openai_cookies.py を実行してください。")
            sys.exit(0)
    elif has_cookies and not args.headless:
        logger.info("Cookie が存在しますが、非ヘッドレスモードで実行します")
        logger.info("Cookie が無効な場合は自動的に再ログインを促します")

    # スクレイパ初期化
    # Note: Cookie が無効な場合は自動的に非ヘッドレスで再起動される
    headless_mode = args.headless
    logger.info(f"Headless mode: {headless_mode}")

    scraper = OpenAIScraper(
        cookie_file=cookie_file,
        headless=headless_mode,
        use_google_auth=True,
    )

    logger.info("=" * 80)
    logger.info(f"OpenAI 請求書取得開始（過去 {args.days} 日分）")
    logger.info("=" * 80)

    try:
        # 請求書取得
        invoices = scraper.fetch_invoices(days=args.days)

        if not invoices:
            logger.warning("請求書が見つかりませんでした")
            return

        logger.info(f"\n取得した請求書 ({len(invoices)}件):")
        for inv in invoices:
            logger.info(f"  {inv.date.strftime('%Y-%m-%d')} - ${inv.amount:.2f} ({inv.invoice_id})")

        # PDFダウンロード
        logger.info(f"\nPDFダウンロード中... → {args.output_dir}")
        invoices = scraper.download_pdfs(invoices, output_dir=args.output_dir)

        # 結果サマリー
        downloaded = [i for i in invoices if i.pdf_path]
        logger.info("\n" + "=" * 80)
        logger.info(f"完了: {len(downloaded)}/{len(invoices)} PDFをダウンロード")
        logger.info("=" * 80)

        for inv in downloaded:
            logger.info(f"  ✓ {inv.pdf_path}")

    except Exception as e:
        logger.error(f"エラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
