#!/usr/bin/env python3
"""
freee-receipt-matcher メインエントリポイント
未処理取引と領収書PDFを自動マッチングして添付
並列処理とキャッシュにより高速化
"""

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from src.clients import FreeeClient, FXRateClient, GmailClient, ReceiptExtractor
from src.core import ReceiptMatcher

# ログ設定
logger = logging.getLogger(__name__)


def setup_logging(log_level: str, log_file: str) -> None:
    """ログ設定"""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)

    # ルートロガー設定
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config(config_path: str) -> dict:
    """設定ファイル読み込み"""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            logger.info(f"Loaded config from {config_path}")
            return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        logger.info("Please create config.yaml from config.yaml.example")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse config file: {e}")
        sys.exit(1)


def load_credentials(config: dict) -> None:
    """
    credentials/ から機密情報を読み込んでconfigにマージ

    Args:
        config: 設定ディクショナリ（in-place更新）
    """
    # freee認証情報
    freee_creds_file = config.get("freee", {}).get("credentials_file")
    if freee_creds_file and Path(freee_creds_file).exists():
        try:
            with open(freee_creds_file, "r") as f:
                freee_creds = yaml.safe_load(f)
                config["freee"]["access_token"] = freee_creds.get("access_token")
                config["freee"]["company_id"] = freee_creds.get("company_id")
                logger.info(f"Loaded freee credentials from {freee_creds_file}")
        except Exception as e:
            logger.error(f"Failed to load freee credentials: {e}")
            sys.exit(1)

    # Claude API キー
    llm_config = config.get("llm", {})
    claude_key = None

    # 1. credentials_file から読み込み（優先）
    creds_file = llm_config.get("credentials_file")
    if creds_file and Path(creds_file).exists():
        try:
            with open(creds_file, "r") as f:
                claude_key = f.read().strip()
                logger.info(f"Loaded Claude API key from {creds_file}")
        except Exception as e:
            logger.warning(f"Failed to load Claude API key from file: {e}")

    # 2. 環境変数から読み込み（フォールバック）
    if not claude_key:
        api_key_env = llm_config.get("api_key_env", "CLAUDE_API_KEY")
        claude_key = os.environ.get(api_key_env)
        if claude_key:
            logger.info(f"Loaded Claude API key from environment variable {api_key_env}")

    if claude_key:
        config["llm"]["api_key"] = claude_key
    else:
        logger.error(
            "Claude API key not found. Set credentials/claude_api_key.txt "
            "or CLAUDE_API_KEY environment variable"
        )
        sys.exit(1)


def parse_args():
    """コマンドライン引数パース"""
    parser = argparse.ArgumentParser(
        description="freee-receipt-matcher: 領収書自動マッチングツール"
    )

    parser.add_argument(
        "--config",
        default="./config.yaml",
        help="設定ファイルパス（デフォルト: ./config.yaml）",
    )

    parser.add_argument(
        "--date-from",
        help="検索開始日（YYYY-MM-DD）",
    )

    parser.add_argument(
        "--date-to",
        help="検索終了日（YYYY-MM-DD）",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="マッチング結果のみ表示（freeeに添付しない）",
    )

    return parser.parse_args()


def main():
    """メイン処理"""
    args = parse_args()

    # 設定読み込み
    config = load_config(args.config)

    # 認証情報読み込み（credentials/から）
    load_credentials(config)

    # ログ設定
    setup_logging(
        config.get("logging", {}).get("level", "INFO"),
        config.get("logging", {}).get("file", "logs/freee-matcher.log"),
    )

    logger.info("=" * 60)
    logger.info("Starting freee-receipt-matcher")
    logger.info("=" * 60)

    # 日付範囲設定
    if args.date_to:
        date_to = datetime.strptime(args.date_to, "%Y-%m-%d").date()
    else:
        date_to = datetime.now().date()

    if args.date_from:
        date_from = datetime.strptime(args.date_from, "%Y-%m-%d").date()
    else:
        date_range_days = config.get("matching", {}).get("date_range_days", 90)
        date_from = date_to - timedelta(days=date_range_days)

    logger.info(f"Date range: {date_from} to {date_to}")

    # 一時ディレクトリ作成
    temp_dir = Path(config.get("temp_dir", "./temp"))
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. クライアント初期化
        logger.info("-" * 60)
        logger.info("Initializing clients")
        logger.info("-" * 60)

        # freee クライアント
        freee_config = config.get("freee", {})
        freee_client = FreeeClient(
            access_token=freee_config.get("access_token"),
            company_id=freee_config.get("company_id"),
        )
        logger.info("Initialized freee client")

        # Gmail クライアント
        gmail_config = config.get("gmail", {})
        gmail_client = GmailClient(
            credentials_path=gmail_config.get("credentials_path"),
            token_path=gmail_config.get("token_path"),
        )
        logger.info("Initialized Gmail client")

        # FX レートクライアント
        fx_config = config.get("fx_rates", {})
        fx_client = FXRateClient(
            cache_dir=fx_config.get("cache_dir", "./cache"),
            provider=fx_config.get("provider", "exchangerate.host"),
        )
        logger.info("Initialized FX rate client")

        # LLM 抽出クライアント（キャッシュ機能付き）
        llm_config = config.get("llm", {})
        extractor = ReceiptExtractor(
            api_key=llm_config.get("api_key"),  # load_credentials()で設定済み
            model=llm_config.get("model", "claude-4-6-sonnet"),
            cache_dir=fx_config.get("cache_dir", "./cache"),  # FXと同じキャッシュディレクトリ
        )
        logger.info("Initialized receipt extractor (with cache)")

        # マッチャー
        matching_config = config.get("matching", {})
        matcher = ReceiptMatcher(
            fx_client=fx_client,
            tolerance_percent=matching_config.get("tolerance_percent", 3.0),
            min_confidence=matching_config.get("min_confidence", 0.7),
        )
        logger.info("Initialized matcher")

        # 2. freee から未処理取引取得
        logger.info("-" * 60)
        logger.info("Fetching unprocessed transactions from freee")
        logger.info("-" * 60)

        all_transactions = freee_client.get_walletables(date_from, date_to)
        logger.info(f"Fetched {len(all_transactions)} transactions")

        # 領収書未添付の取引のみをマッチング対象にする
        transactions = [tx for tx in all_transactions if not tx.has_receipt]
        transactions_with_receipt = [tx for tx in all_transactions if tx.has_receipt]

        logger.info(f"  - Without receipt: {len(transactions)}")
        logger.info(f"  - With receipt (skipped): {len(transactions_with_receipt)}")

        if not transactions:
            logger.info("No transactions without receipts found. Exiting.")
            return

        # 3. Gmail から領収書メール取得
        logger.info("-" * 60)
        logger.info("Searching for receipt emails in Gmail")
        logger.info("-" * 60)

        messages = gmail_client.search_messages(date_from, date_to)
        logger.info(f"Found {len(messages)} receipt emails")

        if not messages:
            logger.info("No receipt emails found. Exiting.")
            return

        # 4. 添付ファイルダウンロード & OCR（並列処理）
        logger.info("-" * 60)
        logger.info("Extracting receipt data from PDFs (parallel processing)")
        logger.info("-" * 60)

        # PDFタスクを準備
        pdf_tasks = []
        for message in messages:
            logger.info(f"Processing message: {message.subject}")
            attachments = gmail_client.get_attachments(message.id)

            for attachment in attachments:
                temp_file = temp_dir / f"{message.id}_{attachment.filename}"
                try:
                    with open(temp_file, "wb") as f:
                        f.write(attachment.data)
                    pdf_tasks.append((str(temp_file), attachment.filename))
                except Exception as e:
                    logger.error(f"Error saving {attachment.filename}: {e}")

        logger.info(f"Starting parallel OCR processing for {len(pdf_tasks)} PDFs (max 5 workers)")

        # 並列処理で OCR 実行
        receipts = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            # タスクを投入
            future_to_pdf = {
                executor.submit(extractor.extract_from_pdf, pdf_path): (pdf_path, filename)
                for pdf_path, filename in pdf_tasks
            }

            # 完了したタスクから順に結果を取得
            for future in as_completed(future_to_pdf):
                pdf_path, filename = future_to_pdf[future]
                try:
                    receipt_data = future.result()
                    if receipt_data:
                        receipts.append(receipt_data)
                        logger.info(f"✓ Extracted: {filename}")
                    else:
                        logger.warning(f"✗ Failed: {filename}")
                except Exception as e:
                    logger.error(f"Error processing {filename}: {e}")

        logger.info(f"Extracted data from {len(receipts)} receipts")

        if not receipts:
            logger.info("No receipt data extracted. Exiting.")
            return

        # 5. マッチング実行
        logger.info("-" * 60)
        logger.info("Matching transactions with receipts")
        logger.info("-" * 60)

        matches, unmatched_txs, unmatched_receipts = matcher.match(transactions, receipts)

        # 6. 結果表示
        logger.info("=" * 60)
        logger.info("MATCHING RESULTS")
        logger.info("=" * 60)

        logger.info(f"\nMatched: {len(matches)}")
        for match in matches:
            logger.info(
                f"  • Transaction {match.transaction.id} ({match.transaction.date}, "
                f"¥{match.transaction.amount:,.0f}) "
                f"→ {match.receipt.source_file} "
                f"(diff: {match.score.amount_diff_pct:.2f}%, conf: {match.score.confidence:.2f})"
            )

        logger.info(f"\nUnmatched transactions: {len(unmatched_txs)}")
        for tx in unmatched_txs:
            logger.info(f"  • {tx}")

        logger.info(f"\nUnmatched receipts: {len(unmatched_receipts)}")
        for receipt in unmatched_receipts:
            logger.info(f"  • {receipt}")

        # 7. freee に添付（dry-run でない場合）
        if args.dry_run:
            logger.info("=" * 60)
            logger.info("DRY RUN MODE - Not attaching receipts to freee")
            logger.info("=" * 60)
        else:
            logger.info("=" * 60)
            logger.info("Attaching receipts to freee")
            logger.info("=" * 60)

            success_count = 0
            fail_count = 0

            for match in matches:
                try:
                    # 領収書アップロード
                    receipt_id = freee_client.upload_receipt(
                        file_path=match.receipt.source_file,
                        receipt_data={
                            "description": match.receipt.merchant_name,
                            "issue_date": match.receipt.date.strftime("%Y-%m-%d"),
                        },
                    )

                    if not receipt_id:
                        logger.error(f"Failed to upload receipt: {match.receipt.source_file}")
                        fail_count += 1
                        continue

                    # 取引に添付
                    success = freee_client.attach_receipt_to_transaction(
                        transaction_id=match.transaction.id,
                        receipt_id=receipt_id,
                    )

                    if success:
                        logger.info(
                            f"✓ Attached receipt to transaction {match.transaction.id}"
                        )
                        success_count += 1
                    else:
                        logger.error(
                            f"✗ Failed to attach receipt to transaction {match.transaction.id}"
                        )
                        fail_count += 1

                except Exception as e:
                    logger.error(f"Error attaching receipt: {e}")
                    fail_count += 1

            logger.info("=" * 60)
            logger.info(f"Attachment complete: {success_count} success, {fail_count} failed")
            logger.info("=" * 60)

        # 8. サマリー
        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total transactions: {len(transactions)}")
        logger.info(f"Total receipts: {len(receipts)}")
        logger.info(f"Matched: {len(matches)}")
        logger.info(f"Unmatched transactions: {len(unmatched_txs)}")
        logger.info(f"Unmatched receipts: {len(unmatched_receipts)}")

        if not args.dry_run and matches:
            logger.info(f"Attachments: {success_count} success, {fail_count} failed")

        logger.info("=" * 60)
        logger.info("freee-receipt-matcher completed successfully")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
